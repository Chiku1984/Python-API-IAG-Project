from flask import Flask
import os
import logging
import logging.config

from .modules import vms, vnics, vdisks, vmactions, foreman, systems, hostgroups, clusters, hosts, hiera, puppet, users, groups, storage
from .config import DefaultConfig


def create_app(app_name=None):
    """Create a Flask app."""

    if app_name is None:
	app_name = DefaultConfig.PROJECT

    app = Flask(app_name, instance_relative_config=True)
    configure_app(app)
    configure_blueprints(app)
    configure_logging(app)

    app.logger.info('Starting UP!')

    return app



def configure_app(app):
    app.config.from_object(DefaultConfig)
    app.config.from_pyfile(DefaultConfig.CONFIG, silent=True)



def configure_blueprints(app):
    app.register_blueprint(foreman.blueprint)
    app.register_blueprint(vms.blueprint)
    app.register_blueprint(vnics.blueprint)
    app.register_blueprint(vdisks.blueprint)
    app.register_blueprint(vmactions.blueprint)
    app.register_blueprint(systems.blueprint)
    app.register_blueprint(hostgroups.blueprint)
    app.register_blueprint(clusters.blueprint)
    app.register_blueprint(hosts.blueprint)
    app.register_blueprint(puppet.blueprint)
    app.register_blueprint(hiera.blueprint)
    app.register_blueprint(users.blueprint)
    app.register_blueprint(groups.blueprint)
    app.register_blueprint(storage.blueprint)



def configure_logging(app):
    logging_conf = app.config.get('LOG_CONFIG')
    if logging_conf and os.path.exists(logging_conf):
        logging.config.fileConfig(logging_conf)
