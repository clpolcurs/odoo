import hashlib

from odoo.tests import HttpCase, new_test_user, tagged

from .common import LearningJapaneseDataCase

READ_GROUPS = "base.group_user,learning_japanese.learning_japanese_view_only_group"
WRITE_GROUPS = "base.group_user,learning_japanese.learning_japanese_admin"


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

        whole = self.call("GET", path, key=self.reader_key)
        self.assertEqual(whole.status_code, 200)
        self.assertEqual(whole.content, sound)
        part = self.call("GET", path, key=self.reader_key, headers={"Range": "bytes=0-3"})
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, sound[:4])

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
