from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

try:
    README = open(os.path.join(here, 'README.md')).read()
except:
    README = 'ESXi Management Utility'

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    "Programming Language :: Python :: 3.6",
]

setup(
    name='esximanager',
    version='1.0.0.0',
    description='ESXi Management Utility',
    classifiers=CLASSIFIERS,
    author='Ryan Chapin',
    author_email='rchapin@nbinteractive.com',
    long_description=README,
    url='',
    python_requires='>=3.6',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'fabric3==1.14.post1',
        ],
    entry_points={
         'console_scripts': [
             'esximanager=esximanager.main:main',
             ],
    },
)
