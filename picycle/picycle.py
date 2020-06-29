import asyncio
import click
import gpsd
import gpxpy
import os
import signal
import sqlite3
import sys
import time

from datetime import datetime
from enum import Enum
from sense_hat import SenseHat, ACTION_PRESSED
from tabulate import tabulate

# -----------------------------------------------------------------------------
# Represents Global State
# -----------------------------------------------------------------------------
class PicycleState(Enum):

    RUNNING = 1
    TERMINATE = 2

class SessionState(Enum):

    READY = 1
    IN_PROGRESS = 2

PICYCLE_STATE = PicycleState.RUNNING
SESSION_STATE = SessionState.READY

# -----------------------------------------------------------------------------
# SenseHAT Joystick Events
# -----------------------------------------------------------------------------
def pushed_left(event):

    global SESSION_STATE

    if event.action == ACTION_PRESSED:

        SESSION_STATE = SessionState.IN_PROGRESS

def pushed_right(event):

    global SESSION_STATE

    if event.action == ACTION_PRESSED:

        SESSION_STATE = SessionState.READY

def pushed_down(event):

    global PICYCLE_STATE

    if event.action == ACTION_PRESSED:

        PICYCLE_STATE = PicycleState.TERMINATE

# Initialize the Sense HAT.
SENSE = SenseHat()

SENSE.stick.direction_left = pushed_left
SENSE.stick.direction_right = pushed_right
SENSE.stick.direction_down = pushed_down

O = (0, 0, 0)
LED_MATRIX = [
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
    O, O, O, O, O, O, O, O,
]

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
# Core asynchronous functions.
# -----------------------------------------------------------------------------
async def loop_led_matrix_update():

    global LED_MATRIX
    global PICYCLE_STATE

    while PICYCLE_STATE == PicycleState.RUNNING:

        SENSE.set_pixels(LED_MATRIX)

        await asyncio.sleep(1)

    click.echo("Stopping LED matrix updates...")

async def loop_track_satellites():

    global LED_MATRIX
    global PICYCLE_STATE

    while PICYCLE_STATE == PicycleState.RUNNING:

        for x in range(gpsd.get_current().sats):

            if x % 2 == 0:

                idx = 0

            else:

                idx = 8

            idx = idx + (x // 2)

            if 0 <= x <= 3:

                LED_MATRIX[idx] = (255, 0, 0)

            elif 3 < x < 8:

                LED_MATRIX[idx] = (255, 255, 0)

            elif 8 <= x <= 16:

                LED_MATRIX[idx] = (0, 255, 0)

        await asyncio.sleep(1)

    click.echo("Stopping tracking satellites...")

async def loop_record_track():

    global LED_MATRIX
    global PICYCLE_STATE
    global SESSION_STATE

    # When run as a service, it's common to encounter SIGTERM. This is needed
    # to clear
    def sigterm_handler(signum, stack_frame):

        global PICYCLE_STATE

        PICYCLE_STATE = PicycleState.TERMINATE

    signal.signal(signal.SIGTERM, sigterm_handler)

    while PICYCLE_STATE == PicycleState.RUNNING:

        for i in range(16, 24):

            LED_MATRIX[i] = (255, 255, 255)

        if SESSION_STATE != SessionState.IN_PROGRESS:

            await asyncio.sleep(1)
            continue

        for i in range(16, 24):

            LED_MATRIX[i] = (0, 0, 255)

        # Get the current date and time, used for creating a new SQLite database.
        now = datetime.now().strftime('%Y%m%d-%H-%M-%S')

        # Connect to the SQLite database.
        db = f"{now}-picycle.sqlite"
        connection = create_connection(db)

        click.echo(click.style(f"New recording session: {db}", fg="yellow"))

        # If the connection is successful, then enter the control loop.
        if connection:

            # Create the database table.
            execute_query(connection, SQLITE_CREATE_TABLE)

            # Gather GPS data and save to the database.
            while PICYCLE_STATE == PicycleState.RUNNING and SESSION_STATE == SessionState.IN_PROGRESS:

                packet = gpsd.get_current()

                # Print the connection status, color coded.
                if packet.mode != 3:

                    click.echo(click.style(
                        f"GPS device connected to {packet.sats} satellites, mode {packet.mode}.",
                        fg="red"
                    ))

                else:

                    click.echo(click.style(
                        f"GPS device connected to {packet.sats} satellites, mode {packet.mode}.",
                        fg="green"
                    ))

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

                await asyncio.sleep(1)

            connection.close()

        # Otherwise report the error and exit.
        else:

            SENSE.show_letter("E", (255, 0, 0))
            time.sleep(3)
            SENSE.clear()
            sys.exit(1)

    click.echo("Stopping recording tracks...")
    SENSE.clear()

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
@click.option("--verbose/--no-verbose", default=False)
def record(verbose):

    SENSE.show_message("Picycle")

    # Connect to the GPS device.
    gpsd.connect()

    # Run the session, consisting of asynchronous tasks.
    asyncio.run(session(verbose))

    # Clear the SenseHAT LED matrix.
    SENSE.clear()

async def session(verbose=False):

    if verbose:

        click.echo("Picycle session has started...")

    # Create an asynchronous task for recording a track.
    task_1 = asyncio.create_task(loop_record_track())

    # Create an asynchronous task for tracking satellites.
    task_2 = asyncio.create_task(loop_track_satellites())

    # Create an asynchronous task for updating the LED matrix.
    task_3 = asyncio.create_task(loop_led_matrix_update())

    # Await for the tasks to complete, then exit.
    await task_1
    await task_2
    await task_3

    if verbose:

        click.echo("Picycle session has ended...")
