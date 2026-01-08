from odoo import models, fields, api
from collections import OrderedDict


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    def _get_gems_stone_mapping(self, score_value):
        """
        Calculate GEMS stones from the final score
        """
        # Format score to 8 digits before decimal
        score_str = str(int(score_value)).zfill(8)

        # Split into 4 sets of 2 digits
        emerald = int(score_str[0:2])
        pearl = int(score_str[2:4])
        ruby = int(score_str[4:6])
        sapphire = int(score_str[6:8])

        # Create mapping dictionary
        gems = {
            'Emerald': emerald,
            'Pearl': pearl,
            'Ruby': ruby,
            'Sapphire': sapphire
        }

        # Sort by value (descending) to find highest
        sorted_gems = OrderedDict(sorted(gems.items(), key=lambda x: x[1], reverse=True))

        # Get primary (highest) and secondary (second highest)
        gem_list = list(sorted_gems.items())
        primary_gem = gem_list[0][0]
        primary_value = gem_list[0][1]
        secondary_gem = gem_list[1][0] if len(gem_list) > 1 else None
        secondary_value = gem_list[1][1] if len(gem_list) > 1 else 0

        return {
            'emerald': emerald,
            'pearl': pearl,
            'ruby': ruby,
            'sapphire': sapphire,
            'primary_gem': primary_gem,
            'primary_value': primary_value,
            'secondary_gem': secondary_gem,
            'secondary_value': secondary_value,
            'formatted_score': score_str
        }
