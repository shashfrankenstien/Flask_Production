
all: dist

test:
	pytest -v .


install:
	python3 -m pip install .


uninstall: clean
	python3 -m pip uninstall flask_production -y


dist:
	python3 -m build


clean:
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info


deploy: dist
	twine upload --verbose -r pypi dist/*


.PHONY: test install uninstall clean deploy
