<p align="center"><img src="logo.png" width="250" alt="Mind the Limit logo"></p>

# Mind the Limit

<p align="center"><b><a href="../README.md#deutsch">🇩🇪 Deutsch</a> · <a href="../README.md#english">🇬🇧 English</a> · <a href="README.fr.md">🇫🇷 Français</a> · <a href="README.it.md">🇮🇹 Italiano</a> · 🇪🇸 Español</b></p>

> **Simon says: mind the limit!** Muestra en directo los límites de uso de Claude Code (sesión, semana, semana del
> modelo) en una Divoom Timebox Evo junto a tu pantalla. Funciona en segundo plano en tu Mac, baja el brillo por la
> noche y, si quieres, se apaga cuando Home Assistant indica que no hay nadie.

<p align="center"><img src="panel.png" width="240" alt="El panel de 16 por 16: 23 en blanco con una barra blanca corta, 35 en naranja con una barra llena aproximadamente un tercio, 0 en violeta con una barra vacía"></p>

## Lo que ves

Tres filas, cada una con un número y una barra de ocho puntos. El color sustituye a la etiqueta:

| Color | Fila | Significado |
|---|---|---|
| blanco | arriba | sesión actual (ventana de cinco horas) |
| naranja | en medio | semana actual, todos los modelos |
| violeta | abajo | semana actual de un modelo con límite propio (por ejemplo Fable) |

A partir del 99 % muestra 99 y una barra llena. Si Mind the Limit no puede leer los límites, la caja muestra un
símbolo rojo grande en lugar de cifras antiguas: <img src="error-usage.png" width="40" alt="signo de interrogación rojo"> = límites no legibles,
<img src="error-claude.png" width="40" alt="C roja"> = no se encontró el comando `claude`.

## Cómo funciona

Cada 5 minutos, Mind the Limit pregunta al propio Claude Code: `claude -p /usage`. Es un comando local sin llamada
al modelo; medido con Claude Code 2.1.276: 0 tokens, 0 USD. La respuesta contiene los límites como datos
estructurados y como texto; primero se lee la estructura, el texto es la alternativa de respaldo. La imagen llega a
la caja por Bluetooth; cada minuto se ajusta el brillo y se mantiene activa la conexión.

## Requisitos

- Un Mac con macOS (desarrollado y probado en macOS 26) y Python 3.10 o posterior, por ejemplo de Homebrew.
- [Claude Code](https://claude.com/claude-code), con la sesión iniciada con una suscripción a Claude (Pro o Max).
  Los límites que se muestran son los de esa suscripción.
- Una [Divoom Timebox Evo](https://divoom.com), enlazada con el Mac en **Ajustes del Sistema → Bluetooth**.

## Instalación

```bash
git clone https://github.com/simon-says-labs/mind-the-limit.git
cd mind-the-limit
python3 -m mind_the_limit install
```

`install` crea su propio entorno de Python con `pyobjc-framework-IOBluetooth` en
`~/Library/Application Support/mind-the-limit`, copia allí el programa y configura el servicio en segundo plano
`labs.simon-says.mind-the-limit`. A partir de entonces el comando es
`~/Library/Application Support/mind-the-limit/mind-the-limit` (si quieres, enlázalo en tu `PATH`):

```bash
mind-the-limit find                          # paired devices with their address
mind-the-limit set device 11-22-33-44-55-66  # starts the background job
mind-the-limit status                        # running?, last values, last problem
```

En la primera conexión, la caja puede cortar y volver a establecer su conexión Bluetooth con el Mac (consulta
[Bluetooth](#bluetooth)). El registro está en `~/Library/Logs/mind-the-limit.log`.

## Ajustes

`mind-the-limit set <key> <value>` guarda el valor y reinicia el servicio en segundo plano.

| Clave | Predeterminado | |
|---|---|---|
| `device` | – | dirección Bluetooth de la caja |
| `interval` | `300` | segundos entre dos lecturas (al menos 60) |
| `night_start`, `night_end` | `23`, `7` | franja nocturna en horas completas |
| `bright_day`, `bright_night` | `60`, `10` | brillo en porcentaje |
| `colors.session`, `colors.week`, `colors.model` | blanco, naranja, violeta | por ejemplo `#00FF88` |
| `ha_dark_states` | `off,not_home` | estados de la entidad de Home Assistant que apagan la caja |
| `claude` | se busca | ruta al comando `claude` si no se encuentra |
| `language` | `auto` | `en`, `de`, `fr`, `it` o `es` para el registro y los comandos |

Probarlo sin caja: `mind-the-limit preview --values 23,35,0 --out panel.png` dibuja la imagen como PNG.

## Home Assistant (opcional)

La caja se apaga mientras una entidad que elijas esté en `off` o `not_home`, por ejemplo «alguna luz encendida» o
tu entidad `person`. Si no se puede acceder a Home Assistant, la caja sigue encendida.

```bash
mind-the-limit connect-ha
```

El asistente comprueba la dirección, abre en el navegador la página **Seguridad** de tu perfil, donde creas un
token de acceso de larga duración, lo recibe sin mostrarlo, lo comprueba y lo guarda en el llavero de macOS, nunca
en un archivo. `mind-the-limit connect-ha --forget` lo vuelve a quitar.

## Bluetooth

La Timebox Evo también es un altavoz. Su puerto serie está en el canal RFCOMM 1; Mind the Limit nunca explora los
canales, porque los intentos fallidos alteran de forma permanente la sesión Bluetooth del proceso y el canal 3 es
el perfil de audio. Si el canal 1 está ocupado (en macOS 26 a veces lo retiene el sistema), Mind the Limit corta
toda la conexión con la caja y la vuelve a establecer. Se oye brevemente si la caja está reproduciendo sonido.

## Seguridad

- Se ejecuta con tu usuario, nunca con `sudo`. Los programas se llaman directamente, nunca a través de una shell.
- El token de Home Assistant se guarda en el llavero y llega a `security` por la entrada estándar, no como
  argumento; nunca aparece en archivos ni en el registro.
- No se borra nada: una versión antigua del programa y `uninstall` van a la Papelera.

Para informar de vulnerabilidades, consulta [SECURITY.md](../SECURITY.md).

## Desarrollo

```bash
python3 -m unittest discover -s tests -t .
```

Las pruebas no necesitan Bluetooth: `tests/fakes.py` sustituye la conexión con la caja. Consulta
[CONTRIBUTING.md](../CONTRIBUTING.md); cambios: [CHANGELOG.md](../CHANGELOG.md).

## Licencia

[MIT](../LICENSE) © 2026 Simon Eckmiller · publicado por [Simon Says](https://github.com/simon-says-labs). La
descripción del protocolo es de Jérôme Wiedemann ([THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).
Este es un proyecto independiente. No está afiliado a Anthropic ni a Divoom ni cuenta con su respaldo. Claude,
Claude Code, Divoom y Timebox son marcas comerciales de sus respectivos propietarios.

<p align="right"><a href="#mind-the-limit">↑ Volver a la selección de idioma</a></p>
