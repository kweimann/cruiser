# 📈 Cruiser Analytics

This is a collection of various scripts for the analysis of game mechanics and the current state of a universe.

# Features
* **Universe heatmap**: Heatmap showing the distribution of players across the galaxies.

# How to use?

First, make sure to install additional packages listed in the `requirements.txt` file in this directory. Now, assuming that you have a terminal open in the project root directory, let's try running the scripts.

#### Universe Heatmap

```shell script
python -m analytics.universe_heatmap --server <server_number> --lang <server_language> [--type occupancy|points] [--max-position <max_position>]
```

Universe heatmap shows the distribution of players across the galaxies. There are two types of distribution you can plot: occupancy distribution and points distribution. Occupancy distribution shows how densely the galaxies are populated. Points distribution shows where the strong players are located.

Consider the following examples of a relatively young universe (about 2 weeks):

![alt text](https://user-images.githubusercontent.com/8287691/82823683-4eaee300-9ea8-11ea-982d-c300b6880270.png "Occupancy distribution of a young universe.")

The plot above is a occupancy distribution. As you can see the most densely populated areas are the first two galaxies, which makes sense because at that time that's where the new players start when they enter the universe.

Below is a points distribution of the same universe (`--type points`). In this example we are interested in the locations of top 100 players in the universe (`--max-position 100`). From this plot, we can see that the beginning of the first galaxy hosts the biggest chunk of the most dangerous players in this server.

![alt text](https://user-images.githubusercontent.com/8287691/82823704-5b333b80-9ea8-11ea-8d33-cb2044aa18c0.png "distribution of top 100 players in a young universe.")
