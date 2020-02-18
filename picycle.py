import click
import gpsd
import gpxpy

from sense_hat import SenseHat
from tabulate import tabulate

def load_gpx_file(gpx_file):

    with open(gpx_file, "r") as f:

        return gpxpy.parse(f)

def save_gpx_file(gpx, gpx_file):

    with open(gpx_file, "w+") as f:

        f.write(gpx.to_xml())

@click.group()
def cli():

    pass

@cli.command()
@click.argument("gpx_file")
def info_gpx(gpx_file):

    gpx = load_gpx_file(gpx_file)

    table = [
        ["Tracks", len(gpx.tracks)],
        ["Waypoints", len(gpx.waypoints)],
        ["Routes", len(gpx.routes)]
    ]

    click.echo(tabulate(table, headers=["Type", "Count"], tablefmt="presto"))

@cli.command()
@click.argument("gpx_file")
def info_tracks(gpx_file):

    gpx = load_gpx_file(gpx_file)

    for track in gpx.tracks:

        click.echo("Track Name: {} | Number: {} | Segments: {}".format(
            track.name,
            track.number,
            len(track.segments)
        ))

        table = []

        for segment in track.segments:

            table.append(["Segment", "", ""])

            for point in segment.points:

                table.append([
                    point.latitude,
                    point.longitude,
                    point.elevation
                ])

        click.echo(tabulate(table, headers=["Latitude", "Longitude", "Elevation"], tablefmt="presto"))

@cli.command()
@click.argument("gpx_file")
def info_waypoints(gpx_file):

    gpx = load_gpx_file(gpx_file)

    table = []

    for waypoint in gpx.waypoints:

        table.append([
            waypoint.name,
            waypoint.latitude,
            waypoint.longitude
        ])

    click.echo(tabulate(table, headers=["Name", "Latitude", "Longitude"], tablefmt="presto"))

@cli.command()
@click.argument("gpx_file")
def info_routes(gpx_file):

    gpx = load_gpx_file(gpx_file)

    table = []

    for route in gpx.routes:

        for point in route.points:

            table.append([
                point.latitude,
                point.longitude,
                point.elevation
            ])

    click.echo(tabulate(table, headers=["Latitude", "Longitude", "Elevation"], tablefmt="presto"))

@cli.command()
def gps():

    gpsd.connect()
    packet = gpsd.get_current()
    print(packet.position())

@cli.command()
def _():

    # This will end up being the primary entry-point for the program when on
    # the bike. There are many actions this function should fulfill:
    #
    # - Initialize a database (lightweight, probably sqlite3) that will keep
    #   track of GPS readings and other metadata during a ride. There should be
    #   a sort of automatic naming scheme here to permit multiple databases to
    #   exist at once; it's common to require multiple recordings throughout a
    #   ride to construct a finalized GPX file.
    #
    # - Initialize the GPS sensor module and load any related libraries for
    #   reading GPS data.
    #
    # - Initialize the control panel and signal to the rider when recording is
    #   available. The primary way the control panel will relay information to
    #   the rider is via LED lights.
    #
    # - Enter an infinite loop that will:
    #
    #   - Wait for user to start recording.
    #   - Once recording, take GPS sensor readings every second and save the
    #     results in the database (the exact metadata to pull from the sensor
    #     has yet to be determined, though latitude, longitude, and elevation
    #     are must-haves).
    #   - Continue until the user stops recording, in which case the GPS sensor
    #     will no longer be pulled from and the database will be saved to the
    #     disk.
    #
    # Saving the database to disk frequently to avoid data-loss is a must,
    # great software engineering skills to catch exceptions and recover are a
    # must.

    sense = SenseHat()

    sense.show_message("Picycle")
