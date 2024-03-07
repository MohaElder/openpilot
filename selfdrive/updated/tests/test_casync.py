import http.server

from asyncio import subprocess
import contextlib
from unittest import mock
from openpilot.selfdrive.test.helpers import http_server_context
from openpilot.selfdrive.updated.tests.test_base import BaseUpdateTest, run, update_release


def DirectoryHttpServer(directory):
  class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
      super().__init__(*args, directory=directory, **kwargs)

  return Handler

def create_casync_release(casync_dir, release, remote_dir):
  run(["casync", "make", casync_dir / f"{release}.caidx", remote_dir])

  hash = run(["casync", "digest", "--without=all", remote_dir], stdout=subprocess.PIPE).stdout.decode().strip()

  with open(casync_dir / f"{release}.digest", "w") as f:
    f.write(hash)


class TestUpdateDCASyncStrategy(BaseUpdateTest):
  def setUp(self):
    super().setUp()
    self.casync_dir = self.mock_update_path / "casync"
    self.casync_dir.mkdir()

  def update_remote_release(self, release):
    update_release(self.remote_dir, release, *self.MOCK_RELEASES[release])
    create_casync_release(self.casync_dir, release, self.basedir)

  def setup_remote_release(self, release):
    self.update_remote_release(release)
    create_casync_release(self.casync_dir, release, self.remote_dir)

  @contextlib.contextmanager
  def additional_context(self):
    with http_server_context(DirectoryHttpServer(self.casync_dir)) as (host, port):
      with mock.patch("openpilot.selfdrive.updated.casync.CHANNEL_PATH", f"http://{host}:{port}"):
        yield
