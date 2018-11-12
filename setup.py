from setuptools import setup

version = open('VERSION').read()
setup(
    name='pyramid_opentracing',
    version=version,
    url='https://github.com/opentracing-contrib/python-pyramid/',
    download_url='https://github.com/opentracing-contrib/python-pyramid/tarball/'+version,
    license='Apache License 2.0',
    author='Carlos Alberto Cortez',
    author_email='calberto.cortez@gmail.com',
    description='OpenTracing support for Pyramid applications',
    long_description=open('README.rst').read(),
    packages=['pyramid_opentracing'],
    platforms='any',
    install_requires=[
        'pyramid',
        'opentracing>=2.0,<2.1'
    ],
    extras_require={
        'tests': [
            'flake8<3',  # see https://github.com/zheller/flake8-quotes/issues/29
            'flake8-quotes',
            'mock<1.1.0',
            'pytest>=2.7,<3',
            'pytest-cov',
        ],
    },
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Framework :: Pyramid',
    ]
)
