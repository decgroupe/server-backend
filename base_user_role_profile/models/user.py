# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_default_profile(self):
        return self.env.ref(
            "base_user_role_profile.default_profile", raise_if_not_found=False
        )

    profile_id = fields.Many2one(
        "res.users.profile",
        "Current profile",
        default=lambda self: self._get_default_profile(),
    )

    profile_ids = fields.Many2many(
        "res.users.profile",
        string="Currently allowed profiles",
    )

    restrict_profile_switching = fields.Boolean(
        "Restrict Profile Switching",
        help="If enabled, the user will be prevented from changing their profile. "
        "This acts as a security measure to "
        "lock users into their current profile.",
    )

    include_default_profile = fields.Boolean(
        "Include Default Profile",
        help="If enabled, the default profile ('no profile') will be added to "
        "the user's allowed profiles. "
        "This allows the user to select a profile that activates only the roles "
        "not associated with any specific profile.",
    )

    def _get_action_root_menu(self):
        # used JS-side. Reload the client; open the first available root menu
        menu = self.env["ir.ui.menu"].search([("parent_id", "=", False)])[:1]
        return {
            "type": "ir.actions.client",
            "tag": "reload",
            "params": {"menu_id": menu.id},
        }

    def action_profile_change(self, vals):
        if not self.restrict_profile_switching:
            self.write(vals)
        return self._get_action_root_menu()

    @api.model
    def create(self, vals):
        new_record = super().create(vals)
        if vals.get("role_line_ids"):
            new_record.sudo()._compute_profile_ids()
        return new_record

    def write(self, vals):
        if not self.env.su and vals.get("profile_id"):
            self.sudo().write({"profile_id": vals["profile_id"]})
            del vals["profile_id"]
        res = super().write(vals)
        if (
            "profile_id" in vals
            or "role_line_ids" in vals
            or "include_default_profile" in vals
        ):
            self.sudo()._compute_profile_ids()
        return res

    def _get_enabled_roles(self):
        res = super()._get_enabled_roles()
        res = res.filtered(
            lambda r: not r.profile_id or (r.profile_id.id == r.user_id.profile_id.id)
        )
        return res

    def _update_profile_id(self):
        default_profile = self._get_default_profile()
        if not self.profile_ids:
            if self.profile_id != default_profile:
                self.profile_id = default_profile
        elif self.profile_id not in self.profile_ids:
            self.write({"profile_id": self.profile_ids[0].id})

    def _compute_profile_ids(self):
        default_profile = self._get_default_profile()
        for rec in self:
            role_lines = rec.role_line_ids
            profiles = role_lines.mapped("profile_id")
            if rec.include_default_profile:
                profiles = default_profile + profiles

            rec.profile_ids = profiles
            # set defaults in case applicable profile changes
            rec._update_profile_id()
