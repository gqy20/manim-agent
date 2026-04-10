"""Package import and structure tests."""

import manim_agent


class TestPackageImport:
    def test_import_package(self):
        """manim_agent 包可以正常导入。"""
        assert manim_agent is not None

    def test_version_exists(self):
        """__version__ 属性存在且为字符串。"""
        assert hasattr(manim_agent, "__version__")
        assert isinstance(manim_agent.__version__, str)
        assert len(manim_agent.__version__) > 0

    def test_version_format(self):
        """版本号符合 semver 格式 (major.minor.patch)。"""
        parts = manim_agent.__version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts)
