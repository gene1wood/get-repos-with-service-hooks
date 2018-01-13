from __future__ import print_function
from agithub.GitHub import GitHub
import json
import re
import os

ORG_NAME = os.environ.get("ORG_NAME", 'mozilla')
REPOS_FILENAME = 'all_repos-{}.json'.format(ORG_NAME)
HOOK_FILENAME = 'all_repo_hooks-{}.json'.format(ORG_NAME)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", '')


def parse_header_links(headers):
    """Return a list of parsed link headers proxies.
    i.e. Link: <http:/.../front.jpeg>; rel=front; type="image/jpeg",<http://.../back.jpeg>; rel=back;type="image/jpeg"
    :rtype: list
    """
    # From https://github.com/requests/requests/blob/master/requests/utils.py
    links = []
    for value in [x[1] for x in headers if x[0].lower() == 'link']:
        replace_chars = ' \'"'
        value = value.strip(replace_chars)
        if not value:
            return links
        for val in re.split(', *<', value):
            try:
                url, params = val.split(';', 1)
            except ValueError:
                url, params = val, ''
            link = {'url': url.strip('<> \'"')}
            for param in params.split(';'):
                try:
                    key, value = param.split('=')
                except ValueError:
                    break
                link[key.strip(replace_chars)] = value.strip(replace_chars)
            links.append(link)
    return links


def paginate(ag):
    data = []
    links = parse_header_links(ag.getheaders())
    for url in [x['url'] for x in links if 'rel' in x and x['rel'] == 'next']:
        print('Fetching url %s' % url)
        status, data = ag.client.get(url)
        data.extend(paginate(ag))
    return data


if not GITHUB_TOKEN:
    print('Missing GITHUB_TOKEN')
    exit(1)

g = GitHub(token=GITHUB_TOKEN)

repos = []
try:
    with open(REPOS_FILENAME) as f:
        repos = json.load(f)
except:
    pass

if len(repos) == 0:
    print('Fetching repos')
    status, repos = g.orgs[ORG_NAME].repos.get()
    repos.extend(paginate(g))
    with open(REPOS_FILENAME, 'w') as f:
        json.dump(repos, f)

#print(len(repos))
#print([x['name'] for x in repos])

hooks = {}
try:
    with open(HOOK_FILENAME) as f:
        hooks = json.load(f)
except:
    pass

for repo in [x['name'] for x in repos]:
    if repo in hooks:
        continue
    print("Checking repo %s : " % (repo,), end='')
    status, data = g.repos[ORG_NAME][repo].hooks.get()
    if status < 200 or status >= 300:
        print("Unexpected error %s : %s" % (status, data))
        exit(1)
    if type(data) != list:
        print("Data is not a list for %s : %s" % (repo, data))
        exit(1)
    data.extend(paginate(g))
    hooks[repo] = data
    print(len(hooks[repo]))
    with open(HOOK_FILENAME, 'w') as f:
        json.dump(hooks, f)

private_repo_hook_map = {}

for repo in hooks:
    if repo not in [x['name'] for x in repos if x['private']]:
        # Skip non private repos
        continue
    private_repos_with_nonweb_hooks = [
        x['name'] for x in hooks[repo] if x['name'] != 'web']
    for private_repo in private_repos_with_nonweb_hooks:
        if private_repo not in private_repo_hook_map:
            private_repo_hook_map[private_repo] = []
        private_repo_hook_map[private_repo].append(repo)

print('Private repos and the nonweb hooks enabled on them')
print(json.dumps(private_repo_hook_map, indent=4))

print('The nonweb hooks which are enabled on any private repos')
print(json.dumps(list(private_repo_hook_map.keys()), indent=4))
