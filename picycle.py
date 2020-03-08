import click
import gpsd
import gpxpy
import os
import sqlite3
import sys
import time

from datetime import datetime
from sense_hat import SenseHat
from tabulate import tabulate

SQLITE_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS picycle (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  latitude FLOAT,
  longitude FLOAT,
  altitude FLOAT,
  speed FLOAT,
  track FLOAT,
  climb FLOAT,
  timestamp TIMESTAMP
);
"""

SQLITE_DROP_TABLE = """
DROP TABLE IF EXISTS picycle;
"""

SQLITE_INSERT= """
INSERT INTO
  picycle (latitude, longitude, altitude, speed, track, climb, timestamp)
VALUES
  (?, ?, ?, ?, ?, ?, ?);
"""

SENSE_HAT_LED_ERROR = [255, 0, 0]

# -----------------------------------------------------------------------------
# Database-related functions.
# -----------------------------------------------------------------------------
def create_connection(path):

    connection = None

    try:

        connection = sqlite3.connect(
            path,
            detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES
        )

        click.echo("Connection to SQLite database successful.")

    except sqlite3.Error as e:

        click.echo(f"Connection to SQLite database failed: '{e}'")

    return connection

def execute_query(connection, query, data=None):

    cursor = connection.cursor()

    try:

        if data:

            cursor.execute(query, data)

        else:

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

def sqlite_to_gpx(points):

    gpx = gpxpy.gpx.GPX()

    # Create the GPX track.
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)

    # Create first segment in our GPX track:
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    # Create points:
    for point in points:

        latitude, longitude, altitude = point

        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
            latitude,
            longitude,
            elevation=altitude
        ))

    return gpx

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
@click.argument('database', type=click.Path(exists=True))
@click.option("--gpx/--no-gpx", default=False)
@click.option("--purge/--no-purge", default=False)
@click.option("--show/--no-show", default=False)
def database(database, gpx, purge, show):

    # Connect to the SQLite database.
    with create_connection(database) as connection:

        # If the connection is successful, then enter the control loop.
        if connection:

            # Option show selected, show the contents of the database.
            if show:

                select_picycle = "SELECT * from picycle"
                picycle = execute_read_query(connection, select_picycle)

                if picycle:

                    table = []

                    for packet in picycle:

                        table.append(list(packet))

                    click.echo(tabulate(
                        table,
                        headers=["ID", "Latitude", "Longitude", "Altitude", "Speed", "Track", "Climb", "Timestamp"],
                        tablefmt="presto"
                    ))

                else:

                    click.echo("Database is empty, no content to show.")

            # Option purge selected, purge the contents of the database.
            if purge:

                execute_query(connection, SQLITE_DROP_TABLE)
                execute_query(connection, SQLITE_CREATE_TABLE)

            # Option gpx selected, convert a subset of the SQLite database to a GPX file.
            if gpx:

                select_picycle = "SELECT latitude, longitude, altitude from picycle"
                points = execute_read_query(connection, select_picycle)

                # Convert the SQLite query results to a GPX object.
                gpx = sqlite_to_gpx(points)

                # Save the GPX file to the disk.
                gpx_file_basename = os.path.splitext(os.path.basename(database))[0]
                gpx_file = f"{gpx_file_basename}.gpx"

                save_gpx_file(gpx, gpx_file)

                click.echo(f"Created GPX file at {gpx_file}")

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

    # Get the current date and time, used for creating a new SQLite database.
    now = datetime.now().strftime('%Y%m%d-%H-%M-%S')

    # Initialize the Sense HAT.
    sense = SenseHat()

    # Connect to the GPS device.
    gpsd.connect()

    # Connect to the SQLite database.
    connection = create_connection(f"{now}-picycle.sqlite")

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
                movement = packet.movement()
                now = packet.get_time()
                speed = movement["speed"]
                track = movement["track"]
                climb = movement["climb"]

                click.echo(f"{latitude}, {longitude}, {altitude}, {speed}, {track}, {climb}, {now}")

                execute_query(
                    connection,
                    SQLITE_INSERT,
                    (latitude, longitude, altitude, speed, track, climb, now)
                )

            except gpsd.NoFixError as e:

                click.echo("GPS device needs at least a 2D fix to provide position information.")

            time.sleep(1)

        connection.close()

    # Otherwise report the error and exit.
    else:

        sense.show_letter("E", SENSE_HAT_LED_ERROR)
        time.sleep(3)
        sense.clear()
        sys.exit(1)
