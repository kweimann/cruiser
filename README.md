# Cruiser 🚀
OGame assistant that keeps your galactic empire safe, notifies you about any potential threats and automates tedious tasks.

# Features
* 🛡️ **Smart fleet saving**: Cruiser watches over your account making sure that all your planets (and moons) are protected. Your fleets and resources will be saved in a way that prevents them from being sniped with sensor phalanx and requires minimum fuel consumption.
* 🔔 **Notifications**: Cruiser notifies you about any hostile events and the actions it takes to protect you.
* 🌌 **Auto expeditions**: Cruiser manages expeditions for you so that you will never again need to worry about having free expeditions slots.

# Installation
1. Install Python `>=3.7.3`
2. Install Python packages `pip install -r requirements.txt`
3. Adjust settings in `config.yaml`
4. Start Cruiser `python start_bot.py`

Optional:
* Setup telegram bot and adjust settings to receive notifications (https://core.telegram.org/bots)

# Contribution
Any contributions are very welcome! Make sure to first post an issue with the features you want to implement and try to stick to the coding style of the project. Happy coding!

# What's inside?
* **OGame client** `ogame/game/client.py` client for scraping information from the game and controlling the account.
* **OGameAPI client** `ogame/api/client.py` client for retrieving information from the official public API.
* **OGame engine** `ogame/game/engine.py` game engine used for calculations e.g. distance between two coordinate systems.
* **OGame bot** `bot/bot.py` implementation of Cruiser's logic, or alternatively, the brain of the operation.
