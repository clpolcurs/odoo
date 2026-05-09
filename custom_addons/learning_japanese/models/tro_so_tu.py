import pykakasi
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


def get_higarana_katakana_romanji(vocabulary: str) -> tuple[str, str, str]:
    kks = pykakasi.kakasi()
    result = kks.convert(vocabulary)
    higarana = "".join([item["hira"] for item in result])
    katakana = "".join([item["kana"] for item in result])
    romanji = " ".join([item["hepburn"] for item in result]).capitalize()
    return higarana, katakana, romanji


class GeneralStuff(models.Model):
    _name = "learning_japanese.general_stuff"
    _description = "Đồ vật nói chung"
    _rec_name = "vocabulary_general_stuff"
    _order = "id asc"

    vocabulary_general_stuff = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_general_stuff",
            "UNIQUE(vocabulary_general_stuff)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_general_stuff")
    def _onchange_vocabulary_general_stuff(self):
        if self.vocabulary_general_stuff:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_general_stuff
            )


class Human(models.Model):
    _name = "learning_japanese.human"
    _description = "Con người"
    _rec_name = "vocabulary_human"
    _order = "id asc"

    vocabulary_human = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_human",
            "UNIQUE(vocabulary_human)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_human")
    def _onchange_vocabulary_human(self):
        if self.vocabulary_human:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_human
            )


class OrdinalNumber(models.Model):
    _name = "learning_japanese.ordinal_number"
    _description = "Số thứ tự"
    _rec_name = "vocabulary_ordinal_number"
    _order = "id asc"

    vocabulary_ordinal_number = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_ordinal_number",
            "UNIQUE(vocabulary_ordinal_number)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_ordinal_number")
    def _onchange_vocabulary_ordinal_number(self):
        if self.vocabulary_ordinal_number:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_ordinal_number
            )


class Times(models.Model):
    _name = "learning_japanese.times"
    _description = "Lần"
    _rec_name = "vocabulary_times"
    _order = "id asc"

    vocabulary_times = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_times",
            "UNIQUE(vocabulary_times)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_times")
    def _onchange_vocabulary_times(self):
        if self.vocabulary_times:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_times
            )


class Ages(models.Model):
    _name = "learning_japanese.ages"
    _description = "Tuổi"
    _rec_name = "vocabulary_ages"
    _order = "id asc"

    vocabulary_ages = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_ages",
            "UNIQUE(vocabulary_ages)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_ages")
    def _onchange_vocabulary_ages(self):
        if self.vocabulary_ages:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_ages
            )


class VatMong(models.Model):
    _name = "learning_japanese.vat_mong"
    _description = "Vật mỏng"
    _rec_name = "vocabulary_vat_mong"
    _order = "id asc"

    vocabulary_vat_mong = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_vat_mong",
            "UNIQUE(vocabulary_vat_mong)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_vat_mong")
    def _onchange_vocabulary_vat_mong(self):
        if self.vocabulary_vat_mong:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_vat_mong
            )


class VatNho(models.Model):
    _name = "learning_japanese.vat_nho"
    _description = "Vật nhỏ"
    _rec_name = "vocabulary_vat_nho"
    _order = "id asc"

    vocabulary_vat_nho = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_vat_nho",
            "UNIQUE(vocabulary_vat_nho)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_vat_nho")
    def _onchange_vocabulary_vat_nho(self):
        if self.vocabulary_vat_nho:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_vat_nho
            )


class VatThonDai(models.Model):
    _name = "learning_japanese.vat_thon_dai"
    _description = "Vật thon dài"
    _rec_name = "vocabulary_vat_thon_dai"
    _order = "id asc"

    vocabulary_vat_thon_dai = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_vat_thon_dai",
            "UNIQUE(vocabulary_vat_thon_dai)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_vat_thon_dai")
    def _onchange_vocabulary_vat_thon_dai(self):
        if self.vocabulary_vat_thon_dai:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_vat_thon_dai
            )


class QuanAo(models.Model):
    _name = "learning_japanese.quan_ao"
    _description = "Quần áo"
    _rec_name = "vocabulary_quan_ao"
    _order = "id asc"

    vocabulary_quan_ao = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana")
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_quan_ao",
            "UNIQUE(vocabulary_quan_ao)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_quan_ao")
    def _onchange_vocabulary_quan_ao(self):
        if self.vocabulary_quan_ao:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_quan_ao
            )


class GiayTat(models.Model):
    _name = "learning_japanese.giay_tat"
    _description = "Giày tất"
    _rec_name = "vocabulary_giay_tat"
    _order = "id asc"

    vocabulary_giay_tat = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_giay_tat",
            "UNIQUE(vocabulary_giay_tat)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_giay_tat")
    def _onchange_vocabulary_giay_tat(self):
        if self.vocabulary_giay_tat:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_giay_tat
            )


class SachVo(models.Model):
    _name = "learning_japanese.sach_vo"
    _description = "Sách vở"
    _rec_name = "vocabulary_sach_vo"
    _order = "id asc"

    vocabulary_sach_vo = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_sach_vo",
            "UNIQUE(vocabulary_sach_vo)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_sach_vo")
    def _onchange_vocabulary_sach_vo(self):
        if self.vocabulary_sach_vo:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_sach_vo
            )


class MayMocXe(models.Model):
    _name = "learning_japanese.may_moc_xe"
    _description = "Máy móc xe"
    _rec_name = "vocabulary_may_moc_xe"
    _order = "id asc"

    vocabulary_may_moc_xe = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_may_moc_xe",
            "UNIQUE(vocabulary_may_moc_xe)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_may_moc_xe")
    def _onchange_vocabulary_may_moc_xe(self):
        if self.vocabulary_may_moc_xe:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_may_moc_xe
            )


class Nha(models.Model):
    _name = "learning_japanese.nha"
    _description = "Nhà"
    _rec_name = "vocabulary_nha"
    _order = "id asc"

    vocabulary_nha = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        ("check_vocabulary_nha", "UNIQUE(vocabulary_nha)", "Tro so tu must be unique"),
    ]

    @api.onchange("vocabulary_nha")
    def _onchange_vocabulary_nha(self):
        if self.vocabulary_nha:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_nha
            )


class Tang(models.Model):
    _name = "learning_japanese.tang"
    _description = "Tầng"
    _rec_name = "vocabulary_tang"
    _order = "id asc"

    vocabulary_tang = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_tang",
            "UNIQUE(vocabulary_tang)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_tang")
    def _onchange_vocabulary_tang(self):
        if self.vocabulary_tang:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_tang
            )


class DoUong(models.Model):
    _name = "learning_japanese.do_uong"
    _description = "Đồ uống"
    _rec_name = "vocabulary_do_uong"
    _order = "id asc"

    vocabulary_do_uong = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_do_uong",
            "UNIQUE(vocabulary_do_uong)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_do_uong")
    def _onchange_vocabulary_do_uong(self):
        if self.vocabulary_do_uong:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_do_uong
            )


class DongVatNhoConTrung(models.Model):
    _name = "learning_japanese.dong_vat_nho_con_trung"
    _description = "Động vật nhỏ, côn trùng"
    _rec_name = "vocabulary_dong_vat_nho_con_trung"
    _order = "id asc"

    vocabulary_dong_vat_nho_con_trung = fields.Char(string="Từ", copy=False)
    higarana = fields.Char(string="Higarana", copy=False)
    katakana = fields.Char(string="Katakana", copy=False)
    romanji = fields.Char(string="Romanji", copy=False)
    vietnamese = fields.Char(string="Nghĩa", copy=False)
    example = fields.Char(string="Ví dụ", copy=False)

    _sql_constraints = [
        (
            "check_vocabulary_dong_vat_nho_con_trung",
            "UNIQUE(vocabulary_dong_vat_nho_con_trung)",
            "Tro so tu must be unique",
        ),
    ]

    @api.onchange("vocabulary_dong_vat_nho_con_trung")
    def _onchange_vocabulary_dong_vat_nho_con_trung(self):
        if self.vocabulary_dong_vat_nho_con_trung:
            self.higarana, self.katakana, self.romanji = get_higarana_katakana_romanji(
                self.vocabulary_dong_vat_nho_con_trung
            )
