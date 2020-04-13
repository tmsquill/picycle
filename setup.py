from setuptools import setup

setup(
    name="picycle",
    version="0.0.1",
    py_modules=["picycle"],
    install_requires=[
        "Click",
        "colorama",
        "gpxpy",
        "tabulate"
    ],
    entry_points="""
        [console_scripts]
        picycle=picycle:cli
    """
)
