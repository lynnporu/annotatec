import setuptools


with open("README.md", mode="r", encoding="utf-8") as file:
    long_description = file.read()

setuptools.setup(
    name="annotatec",
    version="1.0",
    author="Pavlo Tymoshenko",
    author_email="p.tymoshen@gmail.com",
    description="Create annotations for ctypes straight in your C code",
    long_description=long_description,
    python_requires=">=3.8",
    long_description_content_type="text/markdown",
    url="https://github.com/lynnporu/annotatec",
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Plugins",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Code Generators"
    ],
    package_dir={"": "annotatec"},
    packages=setuptools.find_packages(where="annotatec")
)
