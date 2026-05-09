from odoo import http


class VoteApi(http.Controller):
    @http.route('/api/v1/vote-statistics', auth="public", methods=["GET", "POST"], type="json", csrf=False, website=False)
    def get_vote(self, **kw):
        vote_lists = http.request.env['congdoan.baucu.vote_list'].sudo().search([])
        return [
            {
                'id': vote_list.id,
                'name': vote_list.name,
                'total': vote_list.total,
                'elected_number': vote_list.elected_number,
                'vote_details': vote_list.get_vote_details(),
            }
            for vote_list in vote_lists
        ]
