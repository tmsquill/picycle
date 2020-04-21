# Picycle

What happens when you take a bicycle and attach a Raspberry Pi to it? A picycle! It's a POC that utilizes a [Sense HAT](https://www.raspberrypi.org/blog/sense-hat-projects/) and a GPS module to record location and weather data (similar to [Strava](https://www.strava.com/)) on rides.

![Imgur](https://i.imgur.com/blBGR2f.jpg)

Picycle is a CLI tool and is commonly used in two different ways.

## Recording While Riding

Recording location and weather data while riding is done through the `record` sub-command. Obviously the rider won't have a keyboard and screen during a ride, so this command is typically started as a system service (i.e. through [systemd](https://systemd.io/)).

The Sense HAT input (joystick) and output (LED matrix) enable users to interact with picycle in this so-called headless environment.

## Reviewing & Manipulating Recordings

All other sub-commands are meant to be executed in some interactive environment (i.e. SSH, local terminal, etc...). These commands perform various actions; examples include pretty-printing recordings, stitching recording together, and exporting recordings to GPX format.

```bash
$ picycle --help
Usage: picycle [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  database
  info-gpx
  info-routes
  info-tracks
  info-waypoints
  record
```

## Installation

Picycle requires a Python 3 interpreter and utilizes [click](https://click.palletsprojects.com/). Installing locally through `pip` is recommended.

```bash
git clone git@github.com:tmsquill/picycle.git
cd picycle
pip install .
```
