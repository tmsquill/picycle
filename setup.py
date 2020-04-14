from setuptools import setup

setup(
    name="picycle",
    version="0.0.1",
    license="MIT",
    description="Put your Raspberry Pi to good use on a bike ride!",
    author="Troy Squillaci",
    author_email="troysquillaci@gmail.com",
    url="https://github.com/tmsquill/picycle",
    keywords=["raspberry pi", "sense hat", "gps", "sqlite", "bike"]
    py_modules=["picycle"],
    install_requires=[
        "Click",
        "colorama",
        "gpxpy",
        "gpsd-py3",
        "sense_hat",
        "tabulate"
    ],
    entry_points="""
        [console_scripts]
        picycle=picycle:cli
    """
)
