import click
import gpsd
import gpxpy
import sqlite3
import sys
import time

from sense_hat import SenseHat
from tabulate import tabulate

SQLITE_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS picycle (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  latitude FLOAT,
  longitude FLOAT,
  altitude FLOAT
);
"""

SENSE_HAT_ERROR = [255, 0, 0]

# -----------------------------------------------------------------------------
# Database-related functions.
# -----------------------------------------------------------------------------
def create_connection(path):

    connection = None

    try:

        connection = sqlite3.connect(path)
        click.echo("Connection to SQLite database successful.")

    except sqlite3.Error as e:

        click.echo(f"Connection to SQLite database failed: '{e}'")

    return connection

def execute_query(connection, query):

    cursor = connection.cursor()

    try:

        cursor.execute(query)
        connection.commit()
        click.echo("Query execution successful.")

    except sqlite3.Error as e:

        click.echo(f"Query execution failed: '{e}'")

def execute_read_query(connection, query):

    cursor = connection.cursor()
    result = None

    try:

        cursor.execute(query)
        result = cursor.fetchall()

    except sqlite3.Error as e:

        click.echo(f"Read query execution failed: '{e}'")

    return result

# -----------------------------------------------------------------------------
# GPX-related functions.
# -----------------------------------------------------------------------------
def load_gpx_file(gpx_file):

    with open(gpx_file, "r") as f:

        return gpxpy.parse(f)

def save_gpx_file(gpx, gpx_file):

    with open(gpx_file, "w+") as f:

        f.write(gpx.to_xml())

# -----------------------------------------------------------------------------
# Picycle commands.
# -----------------------------------------------------------------------------
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
@click.option("--show/--no-show", default=False)
def database(show):

    # Connect to the SQLite database.
    connection = create_connection("picycle.sqlite")

    # If the connection is successful, then enter the control loop.
    if connection:

        # Show the contents of the table.
        if show:

            select_picycle = "SELECT * from picycle"
            picycle = execute_read_query(connection, select_picycle)

            for packet in picycle:

                print(packet)

    # Otherwise report the error and exit.
    else:

        sys.exit(1)

@cli.command()
def record():

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

    # Initialize the Sense HAT.
    sense = SenseHat()

    # Connect to the SQLite database.
    connection = create_connection("picycle.sqlite")

    # Connect to the GPS device.
    gpsd.connect()

    # If the connection is successful, then enter the control loop.
    if connection:

        sense.show_message("Picycle")

        # Create the database table.
        execute_query(connection, SQLITE_CREATE_TABLE)

        # Gather GPS data and save to the database.
        while True:

            packet = gpsd.get_current()
            click.echo(f"GPS device connected to {packet.sats} satellites, mode {packet.mode}.")

            try:

                latitude, longitude = packet.position()
                altitude = packet.altitude()

                click.echo(f"{latitude}, {longitude}, {altitude}")

                insert_packet = f"""
                INSERT INTO
                  picycle (latitude, longitude, altitude)
                VALUES
                  ({latitude}, {longitude}, {altitude});
                """

                execute_query(connection, insert_packet)

            except gpsd.NoFixError as e:

                click.echo(f"GPS device needs at least a 2D fix to provide position information.")

            time.sleep(1)

    # Otherwise report the error and exit.
    else:

        sense.show_letter("E", SENSE_HAT_ERROR)
        time.sleep(3)
        sense.clear()
        sys.exit(1)
