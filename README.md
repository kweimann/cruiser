# Cruiser 🚀
OGame assistant which keeps your galactic empire safe and notifies you about any potential threats.

# Features
* **Smart fleet saving**: Cruiser watches over your account to make sure all your planets (and moons) are protected. Your fleets and resources will be saved in a way that prevents them from being sniped with sensor phalanx and requires minimum fuel consumption.
* **Telegram notifications**: Cruiser notifies you about any hostile events and the actions it takes to protect you.

# Installation
* Install Python >=3.7.3
* Install requirements: `pip install -r requirements.txt`
* Setup account details in `config.yaml`
* Start bot: `python start_bot.py`
* \[optional\] Setup telegram bot to receive notifications: https://core.telegram.org/bots

# Contribution
Any contributions are very welcome! Make sure to first post an issue with the features you want to implement and try to stick to the coding style of the project. Happy coding!

# TODO
* **Character class support**: due to missing class support some calculations may be slightly off but the functionality remains intact.

# What's inside?
* **OGame client** `ogame/game/client.py`: client for scraping information from the game and controlling the account.
* **OGameAPI client** `ogame//api/client.py`: client for retrieving information from the official public API.
* **OGame engine** `ogame/game/engine.py` game engine used for calculations e.g. distance between two coordinate systems.
* **OGame bot** `bot/bot.py` implementation of Cruiser's logic, or alternatively, the brain of the operation.