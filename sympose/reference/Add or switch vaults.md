# Add or switch vaults

Sympose works with one vault at a time, called the active vault. The chat and the dashboard both use it.

## How do I list the vaults I have?

`VAULT_PATHS` in `.env` lists your vaults as folder paths, separated by commas, and the first one is active by default: `VAULT_PATHS=/Users/me/Obsidian/Main,/Users/me/Obsidian/Work`

## How do I add a second vault?

In the dashboard, open the workspace switcher from the brand mark, type the folder path of the vault and press Enter; it becomes active straight away. Or add its path to `VAULT_PATHS` in `.env`. The folder must already exist.

## How do I switch between vaults?

The workspace switcher in the dashboard lists your vaults, and picking one makes it the active vault. Vaults added there, and your choice of active vault, are remembered in `settings.json` as `added_vaults` and `active_vault`.

## Can I change vault from the terminal?

No. The terminal chat has no command to change vault and uses whichever vault is active, so switch it in the dashboard.

## How do I remove a vault?

There is no remove button yet. A vault from `VAULT_PATHS` is removed by editing `.env`, and one you added is removed by editing `added_vaults` in `settings.json`.
