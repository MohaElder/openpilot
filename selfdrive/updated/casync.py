import os
from pathlib import Path
import shutil
import requests
from openpilot.common.basedir import BASEDIR
from openpilot.selfdrive.updated.common import FINALIZED, STAGING_ROOT, UpdateStrategy, \
                                               get_consistent_flag, get_release_notes, get_version, run, set_consistent_flag
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.updated.git import GitUpdateStrategy


CHANNEL_PATH = "https://commadist.blob.core.windows.net/openpilot-channels"

CHANNELS = {
  "release3": "release",
  "master-ci": "master-ci",
}

CASYNC_PATH = os.path.join(STAGING_ROOT, "casync")


CASYNC_CHANNEL_FILE = "casync_channel.txt"


class CASyncUpdateStrategy(UpdateStrategy):
  def init(self):
    run(["sudo", "rm", "-rf", STAGING_ROOT])
    if os.path.isdir(STAGING_ROOT):
      shutil.rmtree(STAGING_ROOT)

    for dirname in [STAGING_ROOT, CASYNC_PATH]:
      os.mkdir(dirname, 0o755)

  def get_available_channels(self) -> list[str]:
    return list(CHANNELS.keys())

  def get_digest_local(self, path: str) -> str:
    return run(["casync", "digest", "--without=all", path]).strip()

  def get_digest_remote(self, channel: str) -> str:
    return requests.get(f"{CHANNEL_PATH}/{channel}.digest").text.strip()

  def current_channel(self) -> str:
    try:
      with open(Path(BASEDIR) / CASYNC_CHANNEL_FILE) as f:
        return f.read().strip()
    except Exception:
      cloudlog.exception("casync.current_channel")

    try:
      return GitUpdateStrategy.get_branch(BASEDIR)
    except Exception:
      cloudlog.exception("casync.current_channel git")

    return "unknown"

  def update_available(self) -> bool:
    digest_local = self.get_digest_local(BASEDIR)
    digest_remote = self.get_digest_remote(self.target_channel)

    return digest_local != digest_remote

  def describe_channel(self, path):
    version = ""
    channel = self.current_channel()
    try:
      version = get_version(path)
      return f"{version} / {self.current_channel()}"
    except Exception:
      cloudlog.exception("casync.describe_channel")
    return f"{version} / {channel}"

  def release_notes(self, path):
    try:
      return get_release_notes(path)
    except Exception:
      cloudlog.exception("casync.release_notes")
      return ""

  def describe_current_channel(self) -> tuple[str, str]:
    return self.describe_channel(BASEDIR), self.release_notes(BASEDIR)

  def describe_ready_channel(self) -> tuple[str, str]:
    return self.describe_channel(FINALIZED), self.release_notes(FINALIZED)

  def fetch_update(self) -> None:
    cloudlog.info("attempting a casync update inside staging path")
    run(["casync", "extract", f"{CHANNEL_PATH}/{self.target_channel}.caidx", CASYNC_PATH , f"--seed={BASEDIR}"])

  def update_ready(self) -> bool:
    if get_consistent_flag():
      return self.get_digest_local(FINALIZED) == self.get_digest_remote(self.target_channel)
    return False

  def finalize_update(self) -> None:
    """Take the current OverlayFS merged view and finalize a copy outside of
    OverlayFS, ready to be swapped-in at BASEDIR. Copy using shutil.copytree"""

    # Remove the update ready flag and any old updates
    cloudlog.info("creating finalized version of the overlay")
    set_consistent_flag(False)

    # Copy the merged overlay view and set the update ready flag
    if os.path.exists(FINALIZED):
      shutil.rmtree(FINALIZED)
    shutil.copytree(CASYNC_PATH, FINALIZED, symlinks=True)

    with open(Path(FINALIZED) / CASYNC_CHANNEL_FILE) as f:
      f.write(self.target_channel)

    set_consistent_flag(True)
    cloudlog.info("done finalizing overlay")

  def cleanup(self):
    pass
