import unittest
from unittest.mock import MagicMock, patch
from parsers.base import ChapterContent, StoryInfo
from publisher import (
    format_chapter_title_treeiq,
    generate_treeiq_slug,
    build_treeiq_excerpt,
    build_treeiq_body_html,
    build_treeiq_body_text,
    resolve_featured_image_url,
    CMSPublisher
)


class TestTreeIQPublisher(unittest.TestCase):
    def test_format_chapter_title_treeiq_happy_path(self):
        # Happy Path: Tiêu đề chương chuẩn Chapter X - Title
        res = format_chapter_title_treeiq("Chapter 1 - The Shattered Past", 1)
        self.assertEqual(res, "CHAPTER 1 — THE SHATTERED PAST")

        res2 = format_chapter_title_treeiq("CHAPTER 2 — THE BOY WHO SHOULD NOT EXIST", 2)
        self.assertEqual(res2, "CHAPTER 2 — THE BOY WHO SHOULD NOT EXIST")

        res3 = format_chapter_title_treeiq("Chapter 3: The Secret Beneath", 3)
        self.assertEqual(res3, "CHAPTER 3 — THE SECRET BENEATH")

    def test_format_chapter_title_treeiq_edge_cases(self):
        # Edge Case: Chỉ có số hoặc không có từ Chapter
        self.assertEqual(format_chapter_title_treeiq("4. The Final Stand", 4), "CHAPTER 4 — THE FINAL STAND")
        self.assertEqual(format_chapter_title_treeiq("Epilogue", 5), "CHAPTER 5 — EPILOGUE")
        self.assertEqual(format_chapter_title_treeiq("", 1), "CHAPTER 1")

    def test_generate_treeiq_slug(self):
        slug = generate_treeiq_slug("The Boy The Kingdom Feared")
        self.assertTrue(slug.startswith("the-boy-the-kingdom-feared-"))
        self.assertEqual(len(slug.split("-")[-1]), 6)

    def test_build_treeiq_excerpt(self):
        chapters = [
            ChapterContent(
                chapter_number=1,
                title="Chapter 1 - The Beginning",
                paragraphs=[
                    "The bells of Blackthorn Palace had not rung at midnight for seventeen years.",
                    "So when their iron voices suddenly thundered across the sleeping kingdom, King Aldric knew something was terribly wrong."
                ],
                images=[]
            )
        ]
        excerpt = build_treeiq_excerpt(chapters, max_words=20)
        self.assertTrue(excerpt.startswith("CHAPTER 1 — THE BEGINNING"))
        self.assertTrue(len(excerpt.split()) <= 20)

    def test_build_treeiq_body_html_and_text(self):
        chapters = [
            ChapterContent(
                chapter_number=1,
                title="Chapter 1",
                paragraphs=["Para 1", "Para 2"],
                images=[]
            ),
            ChapterContent(
                chapter_number=2,
                title="Chapter 2",
                paragraphs=["Para 3"],
                images=[]
            )
        ]
        html = build_treeiq_body_html(chapters)
        self.assertIn("<h2>CHAPTER 1</h2>", html)
        self.assertIn("<p>Para 1</p>", html)
        self.assertIn("<h2>CHAPTER 2</h2>", html)
        self.assertIn("<p>Para 3</p>", html)

        text = build_treeiq_body_text(chapters)
        self.assertIn("CHAPTER 1\n\nPara 1\n\nPara 2", text)
        self.assertIn("CHAPTER 2\n\nPara 3", text)

    def test_strictly_one_image_per_chapter(self):
        chapter = ChapterContent(
            chapter_number=1,
            title="Chapter 1",
            paragraphs=["Text 1"],
            images=["https://example.com/img1.webp", "https://example.com/img2.webp"],
            content_elements=[
                ("image", "https://example.com/img1.webp"),
                ("text", "![Alt](https://example.com/img3.webp) Some text"),
                ("image", "https://example.com/img4.webp")
            ]
        )
        html = build_treeiq_body_html([chapter])
        self.assertEqual(html.count("<img"), 1)
        self.assertIn("https://example.com/img1.webp", html)
        self.assertNotIn("https://example.com/img3.webp", html)
        self.assertNotIn("https://example.com/img4.webp", html)

    def test_resolve_featured_image_url(self):
        self.assertEqual(resolve_featured_image_url("https://example.com/cover.webp"), "https://example.com/cover.webp")
        self.assertEqual(resolve_featured_image_url("/media/cover.webp", "https://example.com"), "https://example.com/media/cover.webp")
        self.assertEqual(resolve_featured_image_url("local_path.jpg"), "")
        self.assertEqual(resolve_featured_image_url(""), "")

    @patch("requests.Session")
    def test_publish_story_treeiq_happy_path(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # Mock GET /admin/posts/new
        mock_get_res = MagicMock()
        mock_get_res.status_code = 200
        mock_get_res.text = '<form><input name="csrf_token" value="test-token" /></form>'
        mock_get_res.url = "https://vmstoryab.teasy.live/admin/posts/new"
        mock_session.get.return_value = mock_get_res

        # Mock POST /admin/posts
        mock_post_res = MagicMock()
        mock_post_res.status_code = 303
        mock_post_res.headers = {"Location": "/admin/posts/888"}
        mock_session.post.return_value = mock_post_res

        publisher = CMSPublisher("https://vmstoryab.teasy.live", "u", "p")
        publisher.csrf_token = "test-token"

        story = StoryInfo(title="The Boy", slug="the-boy", base_url="https://example.com/story", total_chapters=2)
        chapters = [
            ChapterContent(chapter_number=1, title="Chapter 1", paragraphs=["Text 1"], images=[]),
            ChapterContent(chapter_number=2, title="Chapter 2", paragraphs=["Text 2"], images=[])
        ]

        result = publisher.publish_story(story, chapters)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "888")
        self.assertEqual(result[0]["title"], "THE BOY")
        self.assertTrue(result[0]["url"].startswith("https://vmstoryab.teasy.live/story/the-boy-"))

        # Verify only 1 POST was made to /admin/posts
        post_calls = [c for c in mock_session.post.call_args_list if c[0][0].endswith("/admin/posts")]
        self.assertEqual(len(post_calls), 1)
        sent_data = post_calls[0][1]["data"]
        self.assertEqual(sent_data["title"], "THE BOY")
        self.assertEqual(sent_data["status"], "PUBLISHED")
        self.assertEqual(sent_data["category_id"], "9")
        self.assertIn("CHAPTER 1", sent_data["body_html"])
        self.assertIn("CHAPTER 2", sent_data["body_html"])

    @patch("requests.Session")
    def test_publish_story_treeiq_error_handling(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_post_res = MagicMock()
        mock_post_res.status_code = 400
        mock_post_res.text = '<div class="alert alert-danger">Invalid slug format</div>'
        mock_post_res.json.side_effect = Exception("Not JSON")
        mock_session.post.return_value = mock_post_res

        publisher = CMSPublisher("https://vmstoryab.teasy.live", "u", "p")
        publisher.csrf_token = "test-token"

        story = StoryInfo(title="The Boy", slug="the-boy", base_url="https://example.com/story", total_chapters=1)
        chapters = [ChapterContent(chapter_number=1, title="Chapter 1", paragraphs=["Text"], images=[])]

        result = publisher.publish_story(story, chapters)
        self.assertIsNone(result)
        self.assertIn("400", publisher.last_error)


if __name__ == "__main__":
    unittest.main()
