from setuptools import setup, find_packages

from marcpick import __version__, __author__

with open('README.md', encoding='UTF-8') as fr:
    long_description = fr.read()

setup(
    name='marcpick',
    version=__version__,
    author=__author__,
    description='A Python library for sifting MARC data',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/turricula/marcpick',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)
