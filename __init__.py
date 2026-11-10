from . import models
from . import wizards


def post_init_hook(env):
    """Marca como choferes de la empresa a los empleados cuyo cargo es de chofer o conductor."""
    Empleado = env["hr.employee"].with_context(active_test=False)
    choferes = Empleado.search([
        "|", "|", "|",
        ("job_title", "ilike", "chofer"), ("job_title", "ilike", "conductor"),
        ("job_id.name", "ilike", "chofer"), ("job_id.name", "ilike", "conductor"),
    ])
    choferes.write({"l10n_cl_is_driver": True})
