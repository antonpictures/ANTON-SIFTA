from html.parser import HTMLParser
class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        if tag not in ['meta', 'link', 'br', 'hr', 'img', 'input']:
            self.tags.append(tag)
    def handle_endtag(self, tag):
        if tag not in ['meta', 'link', 'br', 'hr', 'img', 'input']:
            if not self.tags:
                print(f"Error: end tag </{tag}> but no open tags")
            elif self.tags[-1] == tag:
                self.tags.pop()
            else:
                print(f"Error: end tag </{tag}> does not match open tag <{self.tags[-1]}>")

with open('static/index.html', 'r') as f:
    parser = MyHTMLParser()
    parser.feed(f.read())
    print("Open tags remaining:", parser.tags)
