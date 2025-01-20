# Copyright 2024-2025 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# Copyright 2017 ForgeFlow S.L.
# Copyright 2018 Tecnativa - Carlos Dauden, Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"
    _check_company_auto = True

    # Here is the strategy to support bank_account_link = variable
    # without breaking the native behavior
    # company_id is a related of journal_id.company_id
    # When bank_account_link = 'fixed' => we use journal_id
    # When bank_account_link = 'variable':
    # - journal_id is considered as the default journal
    # - alternative_journal_ids are additional journals that can be used
    bank_account_link = fields.Selection(
        [("fixed", "Fixed"), ("variable", "Variable")],
        string="Link to Bank Account",
        required=True,
        default="fixed",
        help="For payment modes that are always attached to the same bank "
        "account of your company (such as wire transfer from customers or "
        "SEPA direct debit from suppliers), select "
        "'Fixed'. For payment modes that are not always attached to the same "
        "bank account (such as SEPA Direct debit for customers, wire transfer "
        "to suppliers), you should select 'Variable', which means that you "
        "will select the bank account on the payment order. If your company "
        "only has one bank account, you should always select 'Fixed'.",
    )
    # I need to explicitly define the table name
    # because I have 2 M2M fields pointing to account.journal
    alternative_journal_ids = fields.Many2many(
        comodel_name="account.journal",
        relation="account_payment_method_line_alternative_journal_rel",
        column1="method_line_id",
        column2="journal_id",
        string="Alternative Bank Journals",
        domain="[('company_id', '=', company_id), "
        "('type', 'in', ('bank', 'cash', 'credit'))]",
        check_company=True,
        compute="_compute_alternative_journal_ids",
        store=True,
        readonly=False,
        precompute=True,
    )
    active = fields.Boolean(default=True)
    report_description = fields.Html(translate=True)
    show_bank_account = fields.Selection(
        selection=[
            ("full", "Full"),
            ("first", "First n chars"),
            ("last", "Last n chars"),
            ("first_last", "First n chars and Last n chars"),
            ("no", "No"),
        ],
        default="full",
        string="Show Customer Bank Account",
        help="On invoice report, show partial or full bank account number.",
    )
    show_bank_account_chars = fields.Integer(
        string="# of Digits to Show for Customer Bank Account",
        default=4,
    )
    refund_payment_mode_id = fields.Many2one(
        comodel_name="account.payment.method.line",
        domain="[('payment_type', '!=', payment_type)]",
        string="Payment Mode for Refunds",
        help="This payment mode will be used when doing "
        "refunds coming from the current payment mode.",
        check_company=True,
    )

    _sql_constraints = [
        (
            "show_bank_account_chars_positive",
            "CHECK(show_bank_account_chars >= 0)",
            "The number of digits to show for customer bank account "
            "must be positive or null.",
        )
    ]

    @api.constrains("bank_account_link", "journal_id", "alternative_journal_ids")
    def _fixed_link_constrains(self):
        for line in self:
            if line.bank_account_link == "fixed" and not line.journal_id:
                raise ValidationError(
                    _(
                        "On %(name)s, Link to Bank Account is "
                        "'Fixed' but the fixed bank journal is not set.",
                        name=line.display_name,
                    )
                )
            if line.payment_method_id.bank_account_required:
                if line.journal_id and not line.journal_id.bank_account_id:
                    raise ValidationError(
                        _(
                            "On %(name)s, the Payment Method %(method)s is "
                            "configured with Bank Account Required but journal "
                            "%(journal)s is not linked to a bank account.",
                            name=line.display_name,
                            method=line.payment_method_id.display_name,
                            journal=line.journal_id.display_name,
                        )
                    )
                if line.bank_account_link == "variable":
                    for journal in line.alternative_journal_ids:
                        if not journal.bank_account_id:
                            raise ValidationError(
                                _(
                                    "On %(name)s, the Payment Method %(method)s is "
                                    "configured with Bank Account Required but journal "
                                    "%(journal)s is not linked to a bank account.",
                                    name=line.display_name,
                                    method=line.payment_method_id.display_name,
                                    journal=journal.display_name,
                                )
                            )

    @api.depends("journal_id", "bank_account_link")
    def _compute_alternative_journal_ids(self):
        for line in self:
            if line.bank_account_link == "fixed":
                line.alternative_journal_ids = [Command.clear()]
            elif (
                line.bank_account_link == "variable"
                and line.journal_id
                and line.journal_id in line.alternative_journal_ids
            ):
                line.alternative_journal_ids = [Command.unlink(line.journal_id.id)]
