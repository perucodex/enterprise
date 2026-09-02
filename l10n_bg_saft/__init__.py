# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models, wizard


def _add_account_saft_code(env):
    bg_coa_companies = env['res.company'].search([('chart_template', '=', 'bg'), ('parent_id', '=', False)])
    for company in bg_coa_companies:
        Template = env['account.chart.template'].with_company(company)
        Template._load_data({'account.account': Template._get_bg_saft_account_code()})


def _update_saft_fields_on_taxes(env):
    bg_coa_companies = env['res.company'].search([('chart_template', '=', 'bg'), ('parent_id', '=', False)])
    for company in bg_coa_companies:
        Template = env['account.chart.template'].with_company(company)
        Template._load_data({'account.tax': Template._get_bg_saft_account_tax()})


def post_init_hooks(env):
    _add_account_saft_code(env)
    _update_saft_fields_on_taxes(env)
