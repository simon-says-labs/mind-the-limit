<p align="center"><img src="logo.png" width="250" alt="Mind the Limit logo"></p>

# Mind the Limit

<p align="center"><b><a href="../README.md#deutsch">🇩🇪 Deutsch</a> · <a href="../README.md#english">🇬🇧 English</a> · 🇫🇷 Français · <a href="README.it.md">🇮🇹 Italiano</a> · <a href="README.es.md">🇪🇸 Español</a></b></p>

> **Simon says: mind the limit!** Affiche en direct les limites d'utilisation de Claude Code (session, semaine,
> semaine du modèle) sur une Divoom Timebox Evo à côté de votre écran. Tourne en arrière-plan sur votre Mac, baisse
> la luminosité la nuit et, si vous le souhaitez, s'éteint quand Home Assistant indique que personne n'est là.

<p align="center"><img src="panel.png" width="240" alt="Le panneau de 16 sur 16 : 23 en blanc avec une courte barre blanche, 35 en orange avec une barre remplie à environ un tiers, 0 en violet avec une barre vide"></p>

## Ce que vous voyez

Trois lignes, chacune avec un nombre et une barre de huit points. La couleur remplace l'étiquette :

| Couleur | Ligne | Signification |
|---|---|---|
| blanc | en haut | session en cours (fenêtre de cinq heures) |
| orange | au milieu | semaine en cours, tous modèles |
| violet | en bas | semaine en cours d'un modèle qui a sa propre limite (par exemple Fable) |

À partir de 99 %, la box affiche 99 et une barre pleine. Si Mind the Limit ne peut pas lire les limites, la box
affiche un grand symbole rouge au lieu d'anciens chiffres : <img src="error-usage.png" width="40" alt="point d'interrogation rouge"> = limites illisibles,
<img src="error-claude.png" width="40" alt="C rouge"> = la commande `claude` est introuvable.

## Comment ça marche

Toutes les 5 minutes, Mind the Limit interroge Claude Code lui-même : `claude -p /usage`. C'est une commande locale
sans appel de modèle ; mesuré avec Claude Code 2.1.276 : 0 tokens, 0 USD. La réponse contient les limites sous forme
de données structurées et de texte ; la structure est lue en premier, le texte sert de solution de repli. L'image
est envoyée à la box par Bluetooth ; chaque minute, la luminosité est ajustée et la connexion maintenue active.

## Prérequis

- Un Mac sous macOS (conçu et testé sur macOS 26) et Python 3.10 ou plus récent, par exemple via Homebrew.
- [Claude Code](https://claude.com/claude-code), connecté avec un abonnement Claude (Pro ou Max). Les limites
  affichées sont celles de cet abonnement.
- Une [Divoom Timebox Evo](https://divoom.com), jumelée avec le Mac dans **Réglages Système → Bluetooth**.

## Installation

```bash
git clone https://github.com/simon-says-labs/mind-the-limit.git
cd mind-the-limit
python3 -m mind_the_limit install
```

`install` crée son propre environnement Python avec `pyobjc-framework-IOBluetooth` dans
`~/Library/Application Support/mind-the-limit`, y copie le programme et met en place le service d'arrière-plan
`labs.simon-says.mind-the-limit`. La commande est ensuite
`~/Library/Application Support/mind-the-limit/mind-the-limit` (vous pouvez la lier dans votre `PATH`) :

```bash
mind-the-limit find                          # paired devices with their address
mind-the-limit set device 11-22-33-44-55-66  # starts the background job
mind-the-limit status                        # running?, last values, last problem
```

Lors de la première connexion, la box peut couper puis rétablir sa connexion Bluetooth avec le Mac (voir
[Bluetooth](#bluetooth)). Le journal se trouve dans `~/Library/Logs/mind-the-limit.log`.

## Réglages

`mind-the-limit set <key> <value>` enregistre la valeur et redémarre le service d'arrière-plan.

| Clé | Par défaut | |
|---|---|---|
| `device` | – | adresse Bluetooth de la box |
| `interval` | `300` | secondes entre deux relevés (au moins 60) |
| `night_start`, `night_end` | `23`, `7` | plage de nuit en heures pleines |
| `bright_day`, `bright_night` | `60`, `10` | luminosité en pourcentage |
| `colors.session`, `colors.week`, `colors.model` | blanc, orange, violet | par exemple `#00FF88` |
| `ha_dark_states` | `off,not_home` | états de l'entité Home Assistant qui éteignent la box |
| `claude` | recherché | chemin de la commande `claude` si elle est introuvable |
| `language` | `auto` | `en`, `de`, `fr`, `it` ou `es` pour le journal et les commandes |

Essayer sans box : `mind-the-limit preview --values 23,35,0 --out panel.png` dessine l'image au format PNG.

## Home Assistant (optionnel)

La box s'éteint tant qu'une entité de votre choix est sur `off` ou `not_home`, par exemple « une lumière allumée »
ou votre entité `person`. Si Home Assistant est injoignable, la box reste allumée.

```bash
mind-the-limit connect-ha
```

L'assistant vérifie l'adresse, ouvre dans le navigateur la page **Sécurité** de votre profil, où vous créez un jeton
d'accès longue durée, le reçoit en saisie masquée, le vérifie et l'enregistre dans le trousseau macOS, jamais dans
un fichier. `mind-the-limit connect-ha --forget` le retire.

## Bluetooth

La Timebox Evo est aussi une enceinte. Son port série se trouve sur le canal RFCOMM 1 ; Mind the Limit ne parcourt
jamais les canaux, car les tentatives échouées perturbent durablement la session Bluetooth du processus et le canal 3
est le profil audio. Si le canal 1 est occupé (sous macOS 26, le système le retient parfois), Mind the Limit coupe
toute la connexion à la box et la rétablit. Cela s'entend brièvement si la box est en train de jouer du son.

## Sécurité

- S'exécute sous votre utilisateur, jamais avec `sudo`. Les programmes sont appelés directement, jamais via un shell.
- Le jeton Home Assistant est conservé dans le trousseau et transmis à `security` par l'entrée standard, pas comme
  argument ; il n'apparaît ni dans des fichiers ni dans le journal.
- Rien n'est supprimé : une ancienne version du programme et `uninstall` vont dans la Corbeille.

Pour signaler une vulnérabilité, voir [SECURITY.md](../SECURITY.md).

## Développement

```bash
python3 -m unittest discover -s tests -t .
```

Les tests n'ont pas besoin de Bluetooth : `tests/fakes.py` remplace la connexion à la box. Voir
[CONTRIBUTING.md](../CONTRIBUTING.md) ; modifications : [CHANGELOG.md](../CHANGELOG.md).

## Licence

[MIT](../LICENSE) © 2026 Simon Eckmiller · publié par [Simon Says](https://github.com/simon-says-labs). La
description du protocole est de Jérôme Wiedemann ([THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).
Ceci est un projet indépendant. Il n'est ni affilié à Anthropic ou Divoom, ni soutenu par eux. Claude, Claude Code,
Divoom et Timebox sont des marques de leurs propriétaires respectifs.

<p align="right"><a href="#mind-the-limit">↑ Retour au choix de la langue</a></p>
