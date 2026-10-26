from types import SimpleNamespace

import pytest

from flask_production.state import host_info


@pytest.mark.parametrize(
	('remote_url', 'expected_url'),
	[
		(
			'https://build-user:secret-token@example.com/org/repo.git',
			'https://example.com/org/repo.git',
		),
		(
			'https://example.com/org/repo.git',
			'https://example.com/org/repo.git',
		),
		(
			'git@example.com:org/repo.git',
			'git@example.com:org/repo.git',
		),
	],
)
def test_get_host_info_git_remote_url(
	monkeypatch,
	remote_url,
	expected_url,
):
	def fake_run(command, **kwargs):
		assert command == ['git', 'remote', 'get-url', 'origin']
		assert kwargs == {'capture_output': True, 'text': True, 'check': True}
		return SimpleNamespace(stdout=remote_url + '\n')

	monkeypatch.setattr(host_info, '_HOST_INFO', {})
	monkeypatch.setattr(host_info.socket, 'gethostname', lambda: 'test-host')
	monkeypatch.setattr(
		host_info.socket,
		'gethostbyname',
		lambda hostname: '127.0.0.1',
	)
	monkeypatch.setattr(
		host_info.subprocess,
		'run',
		fake_run,
	)

	info = host_info.get_host_info()

	assert info['git_url'] == expected_url
