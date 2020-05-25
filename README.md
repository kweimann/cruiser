# 🚀 Cruiser
OGame assistant that keeps your galactic empire safe, notifies you about any potential threats and automates tedious tasks.

# Features
*OGame Version Compatibility*: **7.2.1**

* 🛡️ **Smart fleet saving**: Cruiser watches over your account making sure that all your planets (and moons) are protected. Your fleets and resources will be saved in a way that prevents them from being sniped with sensor phalanx and requires minimum fuel consumption.

* 🔔 **Notifications**: Cruiser notifies you about any hostile events and the actions it takes to protect you.

* 🌌 **Auto expeditions**: Cruiser manages expeditions for you so that you will never again need to worry about having free expedition slots.

# How to use?

If you like what you see but you're not sure how to use it, don't worry - it's simple! Here I'll show you how to run a minimalistic setup for a maximal gain. If you're looking to install Cruiser first, go to [Installation](#installation). 

Now, let's take a look at the [config.yaml](config.yaml). There, we can configure Cruiser to behave exactly how we want it to. You can overwrite the original config file, but I suggest you create a copy and work from there. In this section I'll show you how to create a configuration from scratch. The entire configuration example is available at the end of this section.

#### Minimal Setup

Cruiser only requires you to provide your account information in order to monitor your account and defend it from any attacks. We need to provide all the essential information for Cruiser to not only log in to the account but also to find the server in which it's supposed to play. You can provide the name of the server (e.g. `Universe 1`) or just the server number (e.g. `1`). Additionally, it's mandatory to provide the language of the server as an ISO language code (e.g. `en` for OGame EN):

```yaml
account:
  username: user@example.com
  password: qwerty
  universe: 1
  language: en
```

With this minimal information, Cruiser will be able to log in to the account and watch for hostile fleets. If an attack should be launched on one of our planets, Cruiser will wait until some time before the attack (you can adjust that), and proceed with the defense: 
 
* Cruiser is aware of any returning and deployment fleets and will try to save them too.
* Cruiser automatically determines the best escape destination and sends the fleet with resources there.
* After the attack, Cruiser can recall the saved fleet if the user wants that (must be explicitly set in the configuration; see [config.yaml](config.yaml)).

As you can see, you don't have to configure anything - Cruiser is smart enough to defend your planets (and moons) on its own.

#### Notifications

If you would like to know what happens to your account while you're away, you can setup a Telegram bot that will send you important notifications. Below I've included a quick summary how to setup such bot.

First follow the official tutorial how to create a Telegram bot: https://core.telegram.org/bots#3-how-do-i-create-a-bot. Once you're done you should get a `token` required to authorize your bot. Next, send a dummy message to your bot which will start a chat. Finally you can find the `chat_id` by following this link: `https://api.telegram.org/bot<token>/getUpdates` where `<token>` is the string token you've received in the first step.

Once you have the `token` and `chat_id` you can add Telegram notifications to the configuration file:

```yaml
listeners:
  telegram:
    api_token: <token>
    chat_id: <chat_id>
bot:
  listeners: [telegram]
```

In the config above, we define a new listener called `telegram` with two arguments required to enable messaging: `api_token` and `chat_id`. Then we add `telegram` to the list of listeners in the bot configuration. That's it! 

#### Expeditions

Currently, the meta is to run as many expeditions as humanly possible. Thank god Cruiser is not a human and so it can run more expeditions. 

Let's image that we've just started playing and want to setup a small expedition fleet and have Cruiser resend it as soon as it returns to our home planet at `[1, 115, 8]`. We'll call this expedition `neverending` and assign 5 small cargo ships to it:

```yaml
expeditions:
  neverending:
    origin: [1, 115, 8]
    ships:
      small_cargo: 5
bot:
  expeditions: [neverending]
```

As you can see, you only need to provide the origin and the fleet in order to setup a simple expedition that runs forever. Once defined, you can add expeditions to the list in the bot configuration. Cruiser will happily manage your expeditions and you don't have to do anything. Additionally, Cruiser watches over the galaxy in case your expeditions create debris and sends pathfinders to harvest it.

Below is a list of all valid ship names:

```
small_cargo
large_cargo
light_fighter
heavy_fighter
cruiser
battleship
colony_ship
recycler
espionage_probe
bomber
destroyer
deathstar
battlecruiser
reaper
pathfinder
```

Finally, take a look at the template configuration located in the [config.yaml](config.yaml) file with all possible expeditions settings.


#### Complete Configuration

If you've followed all of the steps above, the entire configuration file should look like this:

```yaml
account:
  username: user@example.com
  password: qwerty
  universe: 1
  language: en

listeners:
  telegram:
    api_token: <token>
    chat_id: <chat_id>

expeditions:
  neverending:
    origin: [1, 115, 8]
    ships:
      small_cargo: 5

bot:
  listeners: [telegram]
  expeditions: [neverending]
```

Don't be afraid to change the configuration whenever you want. Cruiser automatically adjusts to the current state of your account. Therefore it can be restarted at any time without causing any problems. Furthermore, you are free to login from the browser or mobile whenever you want - Cruiser won't mind.

Don't forget to read the template configuration located in the [config.yaml](config.yaml) file. There you will find all possible settings.

If you would like to see a feature that is currently missing, don't hesitate to make a suggestion. Have fun! :)

# Installation
1. Install Python `>=3.7.3`
2. Install Python packages `pip install -r requirements.txt`
3. Setup account information in `config.yaml`
4. Start Cruiser `python start_bot.py`
    * Alternatively: `python start_bot.py --config <path-to-config>` if you're using a different configuration file than [config.yaml](config.yaml).

# 🐋 Docker

For those of you who like to run containers I've included an easy setup to run on a Debian:
1. Build docker image `docker-build.sh`
2. Run docker container `docker-run.sh [--config <path-to-config>]`

The container runs in a background process. You can run `docker attach` to connect to your container. Furthermore, I'm using a restart policy to make sure that the container will be restarted if it suddenly stops running. Finally, you can run `docker stop` to stop the container.

# Contribution
Any contributions are very welcome! Make sure to first post an issue with the features you want to implement and try to stick to the coding style of the project. Happy coding!

# What's inside?
* **OGame client** `ogame/game/client.py` client for scraping information from the game and controlling the account.
* **OGameAPI client** `ogame/api/client.py` client for retrieving information from the official public API.
* **OGame engine** `ogame/game/engine.py` game engine used for calculations e.g. fuel consumption of a fleet.
* **OGame bot** `bot/bot.py` implementation of Cruiser's logic, or alternatively, the brain of the operation.
* **Analytics** `analytics/` collection of various scripts for the analysis of game mechanics and current state of a universe.