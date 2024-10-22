# 🤖 Velodrome and Aerodrome Discord Bots

## Table of Contents

- [Meet the Bots](#meet-the-bots)
- [Pre reqs](#pre-reqs)
- [Running locally](#running-locally)
- [Before you push](#before-you-push)
- [Setting up Bots on Discord](#setting-up-bots-on-discord)

## Meet the Bots

- Commander bot: shows pool stats via `/pool` command
- Fees bot: shows total fees accross all the pools
- Price bot: shows target token price in stable coin
- Rewards bot: shows rewards, fees and incentives for the latest epoch
- TVL bot: shows total value locked across all the pools

## Pre reqs

- [Sugar](https://github.com/velodrome-finance/sugar)
- [Oracle, Velodrome Release](https://github.com/1inch/spot-price-aggregator)
- [Poetry](https://python-poetry.org/)
- [Nox](https://nox.thea.codes/en/stable/)

## Running locally

- `cp .env.example .env`
- set `DISCORD_TOKEN_*` for your bot/bots
- `poetry install`
- `poetry run python -m bots.__main__`

## Before you push

```bash
poetry run nox
```

Got issues with formatting?

```bash
poetry run nox -rs black
```

## Setting up Bots on Discord

- head to [Discord Developer Portal](https://discord.com/developers/applications)
- click `New Application` (top right corner)
- come up with a sensible name for the bot, accept TOS, click `Create`
- click `Bot` in the left hand side panel
- for command bots, enable `MESSAGE CONTENT INTENT`
- click `Reset Token`
- copy newly created token and keep it to share with your trusted dev
- click `OAuth2` in the left had side panel
- click `URL Generator` in the sub menu
- in `Scopes`, select `bot`
- in `Bot Permissions`, select `Change Nickname`; for `Command` bot select `Send Messages` and `Use Slash Commands`
- copy `Generated URL` and open it in a new tab to add bot to your server
- upload emojis from [emojis directory](https://github.com/velodrome-finance/bots/tree/main/emojis) to your discord server (`Server Settings > Emoji`) - these are used to build custom Discord Embed UIs
