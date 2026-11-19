import unittest
from app import create_app

class AppSmokeTests(unittest.TestCase):
    def test_home_endpoint(self):
        app = create_app()
        app.config.update(TESTING=True)
        client = app.test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"html", response.data.lower())

if __name__ == "__main__":
    unittest.main()
