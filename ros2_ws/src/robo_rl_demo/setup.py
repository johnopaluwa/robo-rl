from glob import glob

from setuptools import find_packages, setup


package_name = "robo_rl_demo"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="robo-rl maintainers",
    maintainer_email="maintainers@robo-rl.invalid",
    description="Hardware-free ROS 2 publisher/subscriber practice for robo-rl",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "fake_camera = robo_rl_demo.fake_camera:main",
            "picker = robo_rl_demo.picker:main",
        ],
    },
)
