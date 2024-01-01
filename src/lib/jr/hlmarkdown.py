
import mistletoe


class HlMarkdown:
    def __init__(self, options):
        self.options = options

    def renderMarkdown(self, text):
        if (self.options['forceLinebreaks']):
            text = text.replace('\n','\n\n')
        text = mistletoe.markdown(text)
        return text
