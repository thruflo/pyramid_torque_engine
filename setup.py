#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name = 'pyramid_torque_engine',
    version = '0.5.1',
    description = 'Pyramid and nTorque based dual queue work engine system.',
    author = 'James Arthur',
    author_email = 'username: thruflo, domain: gmail.com',
    url = 'http://github.com/thruflo/pyramid_torque_engine',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Framework :: Pylons',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
    ],
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data = True,
    zip_safe = False,
    install_requires=[
        'fysom',
        # 'ntorque',
        'pyramid_basemodel',
        'pyramid_simpleauth',
        'transaction',
        'zope.interface'
    ],
    tests_require = [
        'coverage',
        'nose',
        'mock'
    ],
    entry_points = {
        'console_scripts': [
            'engine_notification = pyramid_torque_engine.notification_table_executer:run'
        ]
    }
)
