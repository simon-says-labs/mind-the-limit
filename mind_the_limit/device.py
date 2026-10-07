"""The Bluetooth link to the Timebox Evo (macOS, IOBluetooth, RFCOMM).

What this file knows about the box, learned on macOS 26:

* The serial port (SPP) is RFCOMM channel 1. Channels are never scanned: a burst of failed
  opens leaves the Bluetooth session unusable for the rest of the process, and channel 3 is
  the hands-free audio profile.
* An open channel is not proof of a working one. The link counts as up only after the box
  answers a state request (see protocol.is_reply).
* If channel 1 cannot be opened, the system or a crashed program still holds it. The only
  reliable way out is to drop the whole Bluetooth connection to the box (the box is also a
  speaker, so this is audible) and open channel 1 again, which reconnects.

`Timebox` holds the retry logic and works with any link object; `MacLink` is the real one.
Tests use a fake link, so everything but `MacLink` runs without Bluetooth.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

from . import protocol

ATTEMPTS = 4
CHANNEL = 1


class DeviceError(Exception):
    pass


class Timebox:
    def __init__(self, link, log=lambda message: None):
        self.link = link
        self.log = log

    def _verified_open(self) -> bool:
        result = self.link.open()
        if result != 0:
            self.log("open channel %d: result %s" % (CHANNEL, result))
            return False
        self.link.take_received()
        if self.link.write(protocol.state_request()) == 0:
            for _ in range(6):
                self.link.wait(0.5)
                if protocol.is_reply(self.link.peek_received()):
                    self.link.take_received()
                    return True
        self.log("channel %d opened but the box did not answer" % CHANNEL)
        self.link.close()
        return False

    def connect(self) -> None:
        self.link.close()
        pause = 1.0
        for attempt in range(ATTEMPTS):
            if self._verified_open():
                return
            if attempt < ATTEMPTS - 1:
                self.link.drop_connection()
                self.link.wait(pause)
                pause = min(pause * 2, 4.0)
        raise DeviceError("the box did not answer after %d attempts" % ATTEMPTS)

    def send(self, data: bytes, settle: float = 0.3) -> None:
        if not self.link.is_open():
            self.connect()
        if self.link.write(data) != 0:
            self.connect()
            if self.link.write(data) != 0:
                raise DeviceError("writing failed after reconnecting")
        if settle:
            self.link.wait(settle)

    def ping(self) -> bool:
        """Sends a state request and reports whether the box answered within a second."""
        self.link.take_received()
        self.send(protocol.state_request(), settle=0)
        for _ in range(4):
            self.link.wait(0.25)
            if protocol.is_reply(self.link.peek_received()):
                self.link.take_received()
                return True
        return False

    def close(self) -> None:
        self.link.close()


class MacLink:
    """RFCOMM channel 1 to one Bluetooth address, through Apple's IOBluetooth (via PyObjC)."""

    def __init__(self, address: str, channel: int = CHANNEL):
        import objc
        from Foundation import NSDate, NSObject, NSRunLoop
        from IOBluetooth import IOBluetoothDevice

        class _Delegate(NSObject):
            def init(self):
                self = objc.super(_Delegate, self).init()
                if self is None:
                    return None
                self.connected = False
                self.data = bytearray()
                return self

            def rfcommChannelOpenComplete_status_(self, channel, status):
                self.connected = status == 0

            def rfcommChannelData_data_length_(self, channel, data, length):
                self.data.extend(bytes(data[:length]))

            def rfcommChannelClosed_(self, channel):
                self.connected = False

        self._Delegate, self._NSDate, self._NSRunLoop = _Delegate, NSDate, NSRunLoop
        self._Device = IOBluetoothDevice
        self.address, self.channel_id = address, channel
        self.channel, self.delegate = None, None

    def wait(self, seconds: float) -> None:
        self._NSRunLoop.currentRunLoop().runUntilDate_(self._NSDate.dateWithTimeIntervalSinceNow_(seconds))

    def _device(self):
        device = self._Device.deviceWithAddressString_(self.address)
        if device is None:
            raise DeviceError("no Bluetooth device with address %s" % self.address)
        return device

    def open(self) -> int:
        self.delegate = self._Delegate.alloc().init()
        result, channel = self._device().openRFCOMMChannelSync_withChannelID_delegate_(
            None, self.channel_id, self.delegate)
        if result != 0 or channel is None:
            return result or -1
        self.channel = channel
        for _ in range(6):
            if self.delegate.connected:
                return 0
            self.wait(0.5)
        return 0 if self.delegate.connected else -1

    def is_open(self) -> bool:
        return self.channel is not None and self.delegate is not None and self.delegate.connected

    def write(self, data: bytes) -> int:
        if self.channel is None:
            return -1
        return self.channel.writeSync_length_(bytes(data), len(data))

    def peek_received(self) -> bytes:
        return bytes(self.delegate.data) if self.delegate is not None else b""

    def take_received(self) -> bytes:
        data = self.peek_received()
        if self.delegate is not None:
            self.delegate.data.clear()
        return data

    def close(self) -> None:
        if self.channel is not None:
            try:
                self.channel.closeChannel()
            except Exception:
                pass
            self.channel = None
            self.wait(2.0)          # macOS needs a moment before the channel can be opened again

    def drop_connection(self) -> None:
        device = self._Device.deviceWithAddressString_(self.address)
        if device is not None and device.isConnected():
            for _ in range(5):
                device.closeConnection()
                for _ in range(10):
                    self.wait(0.5)
                    if not device.isConnected():
                        break
                if not device.isConnected():
                    break
        self.wait(5.0)              # the box needs a few seconds before it accepts a new channel


def paired_devices():
    """(name, address) of every paired Bluetooth device, for `mind-the-limit find`."""
    from IOBluetooth import IOBluetoothDevice
    found = []
    for device in IOBluetoothDevice.pairedDevices() or []:
        found.append((str(device.name() or "?"), str(device.addressString() or "").upper().replace(":", "-")))
    return sorted(found)
