import base64
import hashlib
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged

from ..services import content_service
from .common import LearningJapaneseDataCase

READ_GROUPS = "base.group_user,learning_japanese.learning_japanese_view_only_group"
WRITE_GROUPS = "base.group_user,learning_japanese.learning_japanese_admin"
# A 1x1 PNG: guess_mimetype must recognise it, so a few header bytes are not enough.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


@tagged("post_install", "-at_install")
class TestApiV1(HttpCase, LearningJapaneseDataCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader_key = cls._key(new_test_user(cls.env, "lj-test-reader", groups=READ_GROUPS))
        cls.writer_key = cls._key(new_test_user(cls.env, "lj-test-writer", groups=WRITE_GROUPS))
        cls.outsider_key = cls._key(new_test_user(cls.env, "lj-test-outsider", groups="base.group_user"))

    @classmethod
    def _key(cls, user):
        return cls.env["res.users.apikeys"].with_user(user).sudo()._generate(None, "test", None)

    def call(self, method, path, key=None, json=None, data=None, headers=None, params=None):
        headers = dict(headers or {})
        if key is not False:
            headers["Authorization"] = f"Bearer {key or self.writer_key}"
        response = self.url_open(f"/api/lj/v1{path}", method=method, json=json, data=data,
                                 headers=headers, params=params, timeout=60)
        self.env.invalidate_all()  # the request wrote through another environment
        return response

    def ok(self, method, path, status=200, **kwargs):
        response = self.call(method, path, **kwargs)
        self.assertEqual(response.status_code, status, response.text)
        return response.json() if response.content else None

    def problem(self, method, path, status, code, **kwargs):
        response = self.call(method, path, **kwargs)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["Content-Type"], "application/problem+json")
        body = response.json()
        self.assertEqual(body["code"], code)
        return body

    # ── authentication and groups ──────────────────────────────────────────────

    def test_requires_a_valid_key(self):
        self.assertEqual(self.call("GET", "/meta", key=False).status_code, 401)
        self.assertEqual(self.call("GET", "/meta", key="not-a-key").status_code, 401)

    def test_groups(self):
        self.problem("GET", "/meta", 403, "forbidden", key=self.outsider_key)
        self.assertFalse(self.ok("GET", "/meta", key=self.reader_key)["user"]["can_write"])
        meta = self.ok("GET", "/meta")
        self.assertTrue(meta["user"]["can_write"])
        self.assertEqual(meta["levels"], ["N5", "N4", "N3", "N2", "N1"])
        self.assertIn("Reading", [tag["name"] for tag in meta["tags"]])
        self.problem("POST", "/comprehensives", 403, "forbidden", key=self.reader_key, json={"title": "x"})

    # ── books ──────────────────────────────────────────────────────────────────

    def test_books(self):
        self.assertEqual(len(self.ok("GET", "/books", params={"ids": f"{self.book.id},{self.book_draft.id}"})["items"]), 2)
        published = self.ok("GET", "/books", params={"published": "true"})["items"]
        self.assertIn(self.book.id, [b["id"] for b in published])
        self.assertNotIn(self.book_draft.id, [b["id"] for b in published])

        response = self.call("GET", f"/books/{self.book.id}")
        book = response.json()
        self.assertEqual(response.headers["ETag"], f'"{book["version"]}"')
        self.assertEqual(book["lessons"], [{
            "id": self.lesson.id, "xid": f"odoo:lesson:{self.lesson.id}", "name": "聴解・課題理解",
            "item_count": 3, "vocabulary_count": 1,
        }])
        self.problem("GET", "/books/999999", 404, "not-found")

        lessons = self.ok("GET", "/lessons", params={"book_id": self.book_draft.id})["items"]
        self.assertEqual([(lesson["id"], lesson["published"]) for lesson in lessons], [(self.lesson_draft.id, False)])

    # ── comprehensives: read ───────────────────────────────────────────────────

    def test_list_filters_and_pages(self):
        # Only look at this test's items: the database may hold real content.
        mine = ",".join(str(i) for i in (self.reading + self.listening + self.grammar + self.draft_item).ids)

        def ids(**params):
            return [item["id"] for item in self.ok("GET", "/comprehensives", params={"ids": mine, **params})["items"]]

        self.assertEqual(ids(tag="Reading"), [self.reading.id, self.draft_item.id])
        self.assertEqual(ids(tag="reading,listening", level="none"), [self.listening.id])
        self.assertEqual(ids(grammar="true"), self.grammar.ids)
        self.assertNotIn(self.grammar.id, ids(grammar="false"))
        self.assertEqual(ids(published="false"), [self.draft_item.id])
        self.assertEqual(ids(q="メッセージ"), [self.reading.id])
        self.assertEqual(ids(lesson_id=self.lesson_draft.id), [self.draft_item.id])
        self.problem("GET", "/comprehensives", 400, "bad-request", params={"tag": "Nope"})
        self.problem("GET", "/comprehensives", 400, "bad-request", params={"level": "N6"})

        first = self.ok("GET", "/comprehensives", params={"ids": mine, "limit": 3})
        self.assertEqual([i["id"] for i in first["items"]], (self.reading + self.listening + self.grammar).ids)
        self.assertNotIn("markup", first["items"][0])
        second = self.ok("GET", "/comprehensives", params={"ids": mine, "limit": 3, "cursor": first["next_cursor"]})
        self.assertEqual([i["id"] for i in second["items"]], self.draft_item.ids)
        self.assertIsNone(second["next_cursor"])
        self.problem("GET", "/comprehensives", 400, "bad-request", params={"cursor": "garbage!"})

    def test_get_item(self):
        response = self.call("GET", f"/comprehensives/{self.reading.id}")
        item = response.json()
        self.assertEqual(response.headers["ETag"], f'"{item["version"]}"')
        self.assertIn("<<係 - かかり>>", item["markup"])
        self.assertIn("<ruby>", item["html_ruby"])
        self.assertTrue(item["published"])
        self.assertTrue(item["is_finalized"])

        grammar = self.ok("GET", f"/comprehensives/{self.grammar.id}")
        self.assertEqual(grammar["title_display"], "N1をN2とする")
        self.assertEqual(grammar["grammar_patterns"], ["とする"])
        self.problem("GET", "/comprehensives/999999", 404, "not-found")

    # ── comprehensives: write ──────────────────────────────────────────────────

    def test_create(self):
        response = self.call("POST", "/comprehensives", json={
            "title": "図書館からのお知らせ", "level": "N3", "tags": ["reading"], "lesson_ids": [self.lesson.id],
            "markup": "<p><<図書館 - としょかん>>は<<休 - やす>>みです。{{Thư viện nghỉ.}}</p>",
        })
        self.assertEqual(response.status_code, 201, response.text)
        item = response.json()
        self.assertEqual(response.headers["Location"], f"/api/lj/v1/comprehensives/{item['id']}")
        self.assertEqual(item["tags"], ["Reading"])
        self.assertEqual(item["book_ids"], [self.book.id])
        self.assertIn("<rt", item["html_ruby"])
        self.assertTrue(item["is_finalized"])
        self.assertTrue(self.env["learning_japanese.audit_log"].search_count(
            [("entity", "=", "comprehensive"), ("res_id", "=", item["id"]), ("op", "=", "create")]))

    def test_create_validation(self):
        body = self.problem("POST", "/comprehensives", 422, "validation-error",
                            json={"level": "N9", "tags": ["Nope"], "colour": "red"})
        self.assertEqual({e["field"] for e in body["errors"]}, {"title", "level", "tags", "colour"})
        self.problem("POST", "/comprehensives", 415, "unsupported-media-type",
                     data="title=x", headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.problem("POST", "/comprehensives", 400, "bad-request",
                     data="{not json", headers={"Content-Type": "application/json"})

    def test_patch_needs_the_current_version(self):
        path = f"/comprehensives/{self.reading.id}"
        version = self.ok("GET", path)["version"]
        self.problem("PATCH", path, 428, "version-required", json={"level": "N3"})
        stale = self.problem("PATCH", path, 412, "version-mismatch", json={"level": "N3"},
                             headers={"If-Match": '"0000000000000000"'})
        self.assertEqual(stale["current_version"], version)

        updated = self.ok("PATCH", path, json={
            "level": "N3", "markup": "<p><<係 - かかり>>の<<人 - ひと>>です。{{Người phụ trách.}}</p>",
        }, headers={"If-Match": f'"{version}"'})
        self.assertEqual(updated["level"], "N3")
        self.assertNotEqual(updated["version"], version)
        self.assertIn("ひと", updated["html_ruby"])
        self.assertIn("<<人 - ひと>>", updated["markup"])
        self.assertEqual(self.reading.level, "N3")

        again = self.ok("PATCH", path, json={"markup": updated["markup"]}, headers={"If-Match": updated["version"]})
        self.assertEqual(again["version"], updated["version"])

    def test_sequence_orders_an_item_in_its_lessons(self):
        path = f"/comprehensives/{self.reading.id}"
        before = self.ok("GET", path, key=self.reader_key)
        self.assertIsNone(before["sequence"])
        current = {"If-Match": f'"{before["version"]}"'}
        for bad in (0, -1, 100_001, "3", 2.5, True):
            body = self.problem("PATCH", path, 422, "validation-error", json={"sequence": bad}, headers=current)
            self.assertEqual([e["field"] for e in body["errors"]], ["sequence"])

        updated = self.ok("PATCH", path, json={"sequence": 3}, headers=current)
        self.assertEqual(updated["sequence"], 3)
        self.assertNotEqual(updated["version"], before["version"])
        self.assertEqual(self.reading.sequence, 3)
        self.assertTrue(self.env["learning_japanese.change_log"].search_count(
            [("entity", "=", "comprehensive"), ("res_id", "=", self.reading.id), ("op", "=", "update")]))
        summary = self.ok("GET", "/comprehensives", key=self.reader_key, params={"lesson_id": self.lesson.id})
        self.assertEqual({i["id"]: i["sequence"] for i in summary["items"]}[self.reading.id], 3)

        # Unset again, the item has the version it had before the field existed.
        cleared = self.ok("PATCH", path, json={"sequence": None}, headers={"If-Match": f'"{updated["version"]}"'})
        self.assertIsNone(cleared["sequence"])
        self.assertEqual(cleared["version"], before["version"])
        self.assertEqual(self.reading.sequence, 0)

        created = self.ok("POST", "/comprehensives", status=201, json={
            "title": "問題1", "lesson_ids": [self.lesson.id], "sequence": 7,
        })
        self.assertEqual(created["sequence"], 7)

    def test_questions_of_an_item_of_the_tests(self):
        path = f"/comprehensives/{self.reading.id}"
        before = self.ok("GET", path, key=self.reader_key)
        self.assertIsNone(before["questions"])
        current = {"If-Match": f'"{before["version"]}"'}
        good = {"no": 1, "choices": 4, "answer": 3, "printed": True,
                "explanation": {"vi": "Giải thích mẫu.", "en": "A sample explanation.", "zh": "示例说明。"}}
        bad_values = (
            [], "x", [good, good], [{**good, "answer": 5}], [{**good, "choices": 5}], [{**good, "choices": 3, "answer": 4}],
            [{**good, "no": 0}], [{**good, "no": True}], [{**good, "printed": 1}], [{**good, "extra": 1}],
            [{k: v for k, v in good.items() if k != "printed"}], [{**good, "explanation": {"en": "only en"}}],
            [{**good, "explanation": {"vi": " "}}], [{**good, "explanation": {"vi": "x", "ko": "y"}}],
            [{**good, "explanation": {"vi": "x" * 4001}}], [{**good, "no": n} for n in range(1, 62)],
        )
        for bad in bad_values:
            body = self.problem("PATCH", path, 422, "validation-error", json={"questions": bad}, headers=current)
            self.assertEqual([e["field"] for e in body["errors"]], ["questions"])

        listening = {"no": 2, "choices": 3, "answer": 1, "printed": False, "explanation": {"vi": "Chỉ có tiếng Việt."}}
        updated = self.ok("PATCH", path, json={"questions": [good, listening]}, headers=current)
        self.assertEqual(updated["questions"], [good, listening])
        self.assertNotEqual(updated["version"], before["version"])
        self.assertEqual(self.reading.questions, [good, listening])
        summary = self.ok("GET", "/comprehensives", key=self.reader_key, params={"lesson_id": self.lesson.id})
        self.assertNotIn("questions", {i["id"]: i for i in summary["items"]}[self.reading.id])

        # Unset again, the item has the version it had before the field existed.
        cleared = self.ok("PATCH", path, json={"questions": None}, headers={"If-Match": f'"{updated["version"]}"'})
        self.assertIsNone(cleared["questions"])
        self.assertEqual(cleared["version"], before["version"])

        created = self.ok("POST", "/comprehensives", status=201, json={
            "title": "問題1", "lesson_ids": [self.lesson.id], "questions": [good],
        })
        self.assertEqual(created["questions"], [good])

    def test_markup_reads_back_as_written(self):
        source = "<p><<夏休 - なつやす>>みに行きます。<br>{{Đi vào <<kỳ nghỉ hè>>.}}</p>"
        item = self.ok("POST", "/comprehensives", status=201, json={
            "title": "夏休み", "level": "N5", "tags": ["reading"], "lesson_ids": [self.lesson.id], "markup": source,
        })
        self.assertEqual(item["markup"], source)
        source = source.replace("行", "<<行 - い>>")
        item = self.ok("PATCH", f"/comprehensives/{item['id']}", json={"markup": source},
                       headers={"If-Match": f'"{item["version"]}"'})
        self.assertEqual(item["markup"], source)
        self.assertIn("kỳ nghỉ hè", item["html_ruby"])

    def test_the_same_markup_converts_stale_html_again(self):
        path = f"/comprehensives/{self.reading.id}"
        fresh = self.ok("GET", path)
        self.reading.with_context(lj_furigana_processed=True).write({"content_only_kanji": "<p>older converter</p>"})
        self.env.flush_all()
        stale = self.ok("GET", path)
        self.assertEqual(stale["html_hover"], "<p>older converter</p>")
        again = self.ok("PATCH", path, json={"markup": stale["markup"]}, headers={"If-Match": f'"{stale["version"]}"'})
        self.assertEqual(again["html_hover"], fresh["html_hover"])
        self.assertEqual(again["version"], fresh["version"])

    def test_delete(self):
        path = f"/comprehensives/{self.listening.id}"
        version = self.ok("GET", path)["version"]
        self.problem("DELETE", path, 403, "forbidden", key=self.reader_key, headers={"If-Match": version})
        self.problem("DELETE", path, 428, "version-required")
        self.assertEqual(self.call("DELETE", path, headers={"If-Match": f'"{version}"'}).status_code, 204)
        self.problem("GET", path, 404, "not-found")

    def test_audio(self):
        path = f"/comprehensives/{self.listening.id}/audio"
        self.problem("GET", path, 404, "not-found")
        self.problem("PUT", path, 415, "unsupported-media-type", data=b"abc", headers={"Content-Type": "text/plain"})

        sound = b"ID3" + bytes(range(256)) * 8
        item = self.ok("PUT", path, data=sound, headers={"Content-Type": "audio/mpeg", "X-Filename": "n2/1ban.mp3"})
        self.assertEqual(item["audio"]["sha1"], hashlib.sha1(sound).hexdigest())
        self.assertEqual(item["audio"]["size"], len(sound))
        self.assertEqual(item["audio"]["mimetype"], "audio/mpeg")
        self.assertEqual(item["audio"]["filename"], "1ban.mp3")
        item = self.ok("PUT", path, data=sound, headers={"Content-Type": "audio/mpeg",
                                                         "X-Filename": "%E8%81%B4%E8%A7%A3%201.mp3"})
        self.assertEqual(item["audio"]["filename"], "聴解 1.mp3")

        whole = self.call("GET", path, key=self.reader_key)
        self.assertEqual(whole.status_code, 200)
        self.assertEqual(whole.content, sound)
        part = self.call("GET", path, key=self.reader_key, headers={"Range": "bytes=0-3"})
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, sound[:4])

    def test_images_shown_by_items(self):
        png = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
        Attachment = self.env["ir.attachment"]
        shown = Attachment.create({"name": "a.png", "raw": png, "mimetype": "image/png",
                                   "res_model": "learning_japanese.comprehensive", "res_id": self.reading.id})
        tagged = Attachment.create({"name": "b.png", "raw": png[:-1], "mimetype": "image/png"})
        hidden = Attachment.create({"name": "c.png", "raw": png, "mimetype": "image/png"})
        pdf = Attachment.create({"name": "d.pdf", "raw": b"%PDF-1.4", "mimetype": "application/pdf"})
        path = f"/comprehensives/{self.reading.id}"
        item = self.ok("GET", path)
        markup = (
            f'<p><img src="/web/image/{shown.id}-{shown.checksum[:8]}/a.png?access_token=7b3b" alt=""></p>'
            f'<p><img src="/web/image/{hidden.id}5-0a1b2c3d/x.png"><img data-attachment-id="{tagged.id}" src="b.png"></p>'
            f'<p><img src="/web/image/{pdf.id}"></p>'
        ) + item["markup"]
        self.ok("PATCH", path, json={"markup": markup}, headers={"If-Match": f'"{item["version"]}"'})

        image = self.call("GET", f"/attachments/{shown.id}", key=self.reader_key)
        self.assertEqual(image.status_code, 200, image.text)
        self.assertEqual(image.content, png)
        self.assertEqual(image.headers["Content-Type"], "image/png")
        self.assertEqual(image.headers["ETag"].strip('"'), hashlib.sha1(png).hexdigest())
        again = self.call("GET", f"/attachments/{shown.id}", key=self.reader_key,
                          headers={"If-None-Match": image.headers["ETag"]})
        self.assertEqual(again.status_code, 304)
        self.assertEqual(self.call("GET", f"/attachments/{tagged.id}", key=self.reader_key).content, png[:-1])
        for attachment_id in (hidden.id, pdf.id, 10**9):
            self.problem("GET", f"/attachments/{attachment_id}", 404, "not-found", key=self.reader_key)
        self.problem("GET", f"/attachments/{shown.id}", 403, "forbidden", key=self.outsider_key)

    def test_upload_images(self):
        path = f"/comprehensives/{self.listening.id}/images"
        png = {"Content-Type": "image/png"}
        self.problem("POST", path, 415, "unsupported-media-type", data=b"<svg/>", headers={"Content-Type": "image/svg+xml"})
        self.problem("POST", path, 415, "unsupported-media-type", data=b"GIF89a" + bytes(64), headers=png)
        self.problem("POST", path, 422, "validation-error", data=b"", headers=png)
        self.problem("POST", path, 403, "forbidden", key=self.reader_key, data=PNG, headers=png)
        self.problem("POST", "/comprehensives/999999999/images", 404, "not-found", data=PNG, headers=png)
        with patch.object(content_service, "IMAGE_MAX_BYTES", 10):
            self.problem("POST", path, 413, "too-large", data=PNG, headers=png)
        self.assertEqual(self.ok("GET", "/meta")["limits"]["image_max_bytes"], content_service.IMAGE_MAX_BYTES)

        image = self.ok("POST", path, status=201, data=PNG, headers={**png, "X-Filename": "%E3%81%88/%E7%B5%B5.png"})
        self.assertEqual(image["name"], "絵.png")
        self.assertEqual(image["sha1"], hashlib.sha1(PNG).hexdigest())
        self.assertEqual(image["size"], len(PNG))
        self.assertEqual(image["mimetype"], "image/png")
        prefix = f"/web/image/{image['attachment_id']}-{image['sha1'][:8]}/%E7%B5%B5.png?access_token="
        self.assertTrue(image["src"].startswith(prefix), image["src"])
        self.assertIn(f'data-attachment-id="{image["attachment_id"]}"', image["html"])
        self.assertEqual(self.ok("POST", path, status=201, data=PNG, headers=png)["name"], "image.png")

        # the image shows only once the markup of an item carries its tag
        attachment = f"/attachments/{image['attachment_id']}"
        self.problem("GET", attachment, 404, "not-found", key=self.reader_key)
        item = self.ok("GET", f"/comprehensives/{self.listening.id}")
        markup = f"<p>{image['html']}</p>" + (item["markup"] or "")
        self.ok("PATCH", f"/comprehensives/{self.listening.id}", json={"markup": markup},
                headers={"If-Match": f'"{item["version"]}"'})
        served = self.call("GET", attachment, key=self.reader_key)
        self.assertEqual(served.status_code, 200, served.text)
        self.assertEqual(served.content, PNG)

    def test_grammar_overrides(self):
        path = f"/comprehensives/{self.reading.id}/grammar-overrides"
        saved = self.ok("PUT", path, json={"items": [{"grammar_id": self.grammar.id, "action": "pin", "note": "とした"}]})
        self.assertEqual(saved["items"], [{"grammar_id": self.grammar.id, "grammar_title": "[Cơ bản] N1をN2とする",
                                           "action": "pin", "note": "とした"}])
        self.assertEqual(self.ok("GET", path)["items"], saved["items"])
        body = self.problem("PUT", path, 422, "validation-error",
                            json={"items": [{"grammar_id": self.listening.id, "action": "pin"}]})
        self.assertEqual(body["errors"][0]["field"], "grammar_id")
        cleared = self.ok("PUT", path, json={"items": []})
        self.assertEqual(cleared["items"], [])

    def test_audio_cues(self):
        item_path = f"/comprehensives/{self.listening.id}"
        path = f"{item_path}/audio-cues"
        # 何 is the 7th character of the second cue: the audio reaches it at 3.3 s (NihonGo ADR-089)
        cues = [{"text": "F: すみません。", "start_ms": 1200, "end_ms": 2900},
                {"text": "M: はい、何でしょう。", "start_ms": 2900, "end_ms": 4400, "marks": [[6, 3300]]}]
        self.assertIsNone(self.ok("GET", path, key=self.reader_key)["audio_cues"])
        self.problem("PUT", path, 409, "conflict", json={"audio_sha1": "0" * 40, "cues": cues})

        sound = b"ID3" + bytes(range(256)) * 8
        item = self.ok("PUT", f"{item_path}/audio", data=sound, headers={"Content-Type": "audio/mpeg"})
        sha1 = item["audio"]["sha1"]
        self.problem("PUT", path, 409, "conflict", json={"audio_sha1": "0" * 40, "cues": cues})
        self.problem("PUT", path, 400, "bad-request", json={"audio_sha1": sha1})
        body = self.problem("PUT", path, 422, "validation-error", json={"audio_sha1": sha1, "cues": [
            {"text": " ", "start_ms": 100, "end_ms": 50},
            {"text": "M: はい。", "start_ms": 10, "end_ms": 20, "speaker": "M"},
            {"text": "F: ええ。", "start_ms": True, "end_ms": 30},
        ]})
        self.assertEqual({(e["index"], e.get("field")) for e in body["errors"]},
                         {(0, "text"), (0, "end_ms"), (1, "start_ms"), (1, "speaker"), (2, "start_ms")})
        body = self.problem("PUT", path, 422, "validation-error", json={"audio_sha1": sha1, "cues": [
            {"text": "F: すみません。", "start_ms": 1200, "end_ms": 2900, "marks": [[0, 1300]]},
            {"text": "M: はい、何でしょう。", "start_ms": 2900, "end_ms": 4400, "marks": [[7, 3300], [6, 3400]]},
            {"text": "F: ええ。", "start_ms": 4400, "end_ms": 5000, "marks": [[3, 5000]]},
            {"text": "M: そう。", "start_ms": 5000, "end_ms": 5600, "marks": [["3", 5100]]},
        ]})
        self.assertEqual({(e["index"], e.get("field")) for e in body["errors"]},
                         {(0, "marks"), (1, "marks"), (2, "marks"), (3, "marks")})
        self.problem("PUT", path, 403, "forbidden", key=self.reader_key, json={"audio_sha1": sha1, "cues": cues})
        self.problem("PUT", path, 412, "version-mismatch", json={"audio_sha1": sha1, "cues": cues},
                     headers={"If-Match": '"stale"'})

        saved = self.ok("PUT", path, json={"audio_sha1": sha1, "cues": cues},
                        headers={"If-Match": f'"{item["version"]}"'})
        self.assertEqual(saved["audio_cues"], {"audio_sha1": sha1, "cues": cues})
        self.assertNotEqual(saved["version"], item["version"])
        self.assertEqual(self.ok("GET", path, key=self.reader_key), saved)
        full = self.ok("GET", item_path)
        self.assertEqual((full["audio_cues"], full["version"]), (saved["audio_cues"], saved["version"]))
        summary = self.ok("GET", "/comprehensives", params={"ids": str(self.listening.id), "view": "summary"})
        self.assertNotIn("audio_cues", summary["items"][0])
        self.assertEqual(summary["items"][0]["version"], saved["version"])

        audit_log = self.env["learning_japanese.audit_log"]
        logged = [("entity", "=", "comprehensive"), ("res_id", "=", self.listening.id), ("op", "=", "audio_cues")]
        self.assertEqual(audit_log.search_count(logged), 1)
        self.assertEqual(self.ok("PUT", path, json={"audio_sha1": sha1, "cues": cues}), saved)
        self.assertEqual(audit_log.search_count(logged), 1)  # the same cues again: no change, no audit

        cleared = self.ok("PUT", path, json={"cues": []})
        self.assertIsNone(cleared["audio_cues"])
        # An item without cues keeps the version it had before the API gained them.
        self.assertEqual(cleared["version"], item["version"])

    # ── vocabularies ───────────────────────────────────────────────────────────

    def test_vocabulary(self):
        created = self.ok("POST", "/vocabularies", 201, json={
            "term": "試話します", "hiragana": "しわします", "meaning_vi": "nói thử", "level": "N5",
            "verb_group": "group1", "forms": {"te": "試話して", "past": "試話した"}, "lesson_ids": [self.lesson.id],
        })
        self.assertEqual(created["verb_group"], "group1")
        self.assertEqual(created["forms"]["te"], "試話して")
        self.assertTrue(created["published"])
        self.problem("POST", "/vocabularies", 409, "conflict", json={"term": "試話します", "meaning_vi": "nói thử"})

        path = f"/vocabularies/{created['id']}"
        updated = self.ok("PATCH", path, json={"honorific_type": "kenjougo", "forms": {"te": None}},
                          headers={"If-Match": created["version"]})
        self.assertEqual(updated["honorific_type"], "kenjougo")
        self.assertIsNone(updated["forms"]["te"])
        self.assertEqual(updated["forms"]["past"], "試話した")

        found = self.ok("GET", "/vocabularies", params={"q": "しわし"})["items"]
        self.assertEqual([v["id"] for v in found], [created["id"]])

    def test_vocabulary_meanings_in_english_and_chinese(self):
        created = self.ok("POST", "/vocabularies", 201, json={
            "term": "試冷めます", "meaning_vi": "nguội", "meaning_en": "cool down", "meaning_zh": "凉",
            "lesson_ids": [self.lesson.id],
        })
        self.assertEqual((created["meaning_en"], created["meaning_zh"]), ("cool down", "凉"))
        record = self.env["learning_japanese.vocabulary"].browse(created["id"])
        self.assertEqual((record.english, record.chinese), ("cool down", "凉"))

        path = f"/vocabularies/{created['id']}"
        updated = self.ok("PATCH", path, json={"meaning_en": "  get cold ", "meaning_zh": None},
                          headers={"If-Match": created["version"]})
        self.assertEqual((updated["meaning_en"], updated["meaning_zh"]), ("get cold", None))
        self.assertNotEqual(updated["version"], created["version"])
        body = self.problem("PATCH", path, 422, "validation-error", json={"meaning_zh": 3},
                            headers={"If-Match": updated["version"]})
        self.assertEqual(body["errors"][0]["field"], "meaning_zh")

        saved = self.ok("POST", "/vocabularies/bulk", json={"items": [
            {"id": created["id"], "meaning_zh": "变凉"},
        ]})["items"]
        self.assertEqual(saved[0]["meaning_zh"], "变凉")

    def test_vocabulary_bulk_is_all_or_nothing(self):
        Vocabulary = self.env["learning_japanese.vocabulary"]
        before = Vocabulary.search_count([])
        body = self.problem("POST", "/vocabularies/bulk", 422, "validation-error", json={"items": [
            {"term": "試読みます", "meaning_vi": "đọc thử"},
            {"term": "試書きます", "level": "N9"},
        ]})
        self.assertEqual([(e["index"], e["field"]) for e in body["errors"]], [(1, "level")])
        self.assertEqual(Vocabulary.search_count([]), before)

        saved = self.ok("POST", "/vocabularies/bulk", json={"items": [
            {"term": "試読みます", "meaning_vi": "đọc thử"},
            {"id": self.vocabulary.id, "level": "N2"},
        ]})["items"]
        self.assertEqual([v["term"] for v in saved], ["試読みます", "理解します"])
        self.assertEqual(self.vocabulary.level, "N2")

    # ── markup, QA ─────────────────────────────────────────────────────────────

    def test_markup_preview(self):
        result = self.ok("POST", "/markup/preview", key=self.reader_key,
                         json={"markup": "<p><<人>>と<<話 - はな>>す。体力</p>"})
        self.assertIn("<ruby>", result["html_ruby"])
        self.assertEqual({i["code"] for i in result["issues"]}, {"auto_reading", "kanji_without_reading"})
        self.assertEqual(result["stats"]["markers"], 2)

    def test_qa_issues(self):
        page = self.ok("GET", "/qa/issues", key=self.reader_key)
        by_id = {item["id"]: {i["code"] for i in item["issues"]} for item in page["items"]}
        self.assertEqual(by_id[self.listening.id], {"missing_level", "missing_markup", "missing_audio"})
        self.assertEqual(by_id[self.reading.id], {"auto_readings"})
        self.assertNotIn(self.grammar.id, by_id)
        self.assertGreaterEqual(page["summary"]["missing_level"], 1)

        drafts = self.ok("GET", "/qa/issues", params={"code": "not_published", "book_id": self.book_draft.id})["items"]
        self.assertEqual([item["id"] for item in drafts], [self.draft_item.id])
        self.problem("GET", "/qa/issues", 400, "bad-request", params={"code": "bogus"})

    # ── sync ───────────────────────────────────────────────────────────────────

    def test_changes_and_snapshot(self):
        head = self.ok("GET", "/changes/head", key=self.reader_key)["cursor"]
        version = self.ok("GET", f"/comprehensives/{self.grammar.id}")["version"]
        self.ok("PATCH", f"/comprehensives/{self.grammar.id}", json={"grammar_patterns": ["とする", "として"]},
                headers={"If-Match": version})
        feed = self.ok("GET", "/changes", key=self.reader_key, params={"after": head})
        self.assertIn(("comprehensive", self.grammar.id, "update"),
                      {(e["entity"], e["id"], e["op"]) for e in feed["events"]})
        self.assertFalse(feed["has_more"])
        self.assertEqual(self.ok("GET", "/changes", params={"after": feed["next_after"]})["events"], [])
        self.problem("GET", "/changes", 400, "bad-request", params={"after": "x-y"})

        snapshot = self.ok("GET", "/snapshot/comprehensives", key=self.reader_key)
        published = {i["id"] for i in snapshot["items"]}
        self.assertLessEqual({self.reading.id, self.listening.id, self.grammar.id}, published)
        self.assertNotIn(self.draft_item.id, published)
        self.assertTrue(snapshot["feed_cursor"])
        everything = self.ok("GET", "/snapshot/comprehensives", params={"published_only": "false", "tag": "Reading"})
        readings = {i["id"] for i in everything["items"]}
        self.assertLessEqual({self.reading.id, self.draft_item.id}, readings)
        self.assertNotIn(self.listening.id, readings)
        self.problem("GET", "/snapshot/nothing", 404, "not-found")
