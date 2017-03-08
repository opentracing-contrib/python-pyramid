from setuptools import setup

version = open('VERSION').read()
setup(
    name='pyramid_opentracing',
    version=version,
    url='https://github.com/carlosalberto/python-pyramid/',
    download_url='https://github.com/carlosalberto/python-pyramid/tarball/'+version,
    license='BSD',
    author='Carlos Alberto Cortez',
    author_email='calberto.cortez@gmail.com',
    description='OpenTracing support for Pyramid applications',
    long_description=open('README.rst').read(),
    packages=['pyramid_opentracing'],
    platforms='any',
    install_requires=[
        'pyramid',
        'opentracing>=1.1,<1.2'
    ],
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
