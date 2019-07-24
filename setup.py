import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="TermoClient",
    version="0.1.0",
    author="Juan Jose Nicola",
    author_email="jjnicola@greenbone.net",
    description="A small daemon to fetch info from a device.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jjnicola/termoclient",
    
    packages=['termoclient',],
    entry_points={
        'console_scripts': [
            'termoclient=termoclient.termoclient:main',
        ],
    },
    
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
    ],
)
