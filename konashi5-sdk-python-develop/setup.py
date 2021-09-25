import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="konashi",
    version="0.1.0",
    author="Sebastian MILLER",
    author_email="sebastian@ux-xu.com",
    description="Konashi SDK for Python3",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YUKAI/konashi5-sdk-python",
    project_urls={
        "Bug Tracker": "https://github.com/YUKAI/konashi5-sdk-python/issues",
    },
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        'bleak >= 0.10.0',
    ],
)

