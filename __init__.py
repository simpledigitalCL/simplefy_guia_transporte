from . import models
from . import wizards


def post_init_hook(env):
    """Crea el transporte para la guía de cada vehículo de la Flota que ya tenga patente."""
    env["fleet.vehicle"].with_context(active_test=False).search([])._l10n_cl_sync_transport()
