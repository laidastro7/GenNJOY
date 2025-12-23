from setuptools import setup, find_packages

setup(
    name="gennjoy",
    version="1.0.0",
    description="Automated Nuclear Data Processing Framework (NJOY + OpenMC)",
    author="Dr. Mohamed Laid YAHIAOUI et al.",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "numpy",
        "pandas",
        "scipy",
        "h5py",
        "lxml",
        "requests",
        "beautifulsoup4",
        "colorama",
        "openmc"  
    ],
    entry_points={
        "console_scripts": [
            "gennjoy=gennjoy.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Physics",
    ],
)