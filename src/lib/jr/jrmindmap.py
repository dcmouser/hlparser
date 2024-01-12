# imports
from lib.jr import jrfuncs
from lib.jr import jroptions
from lib.jr.jrfuncs import jrprint
from lib.jr.jrfuncs import jrException

# python imports
import os
import pathlib
import json
import re

# graphviz
import graphviz


# ---------------------------------------------------------------------------
class JrMindMap:
    def __init__(self, options={}):
        self.options = options
        #
        self.nodes = {}
        # test
        os.environ["PATH"] += os.pathsep + 'C:/Program Files/Graphviz/bin'




# ---------------------------------------------------------------------------
    def debug(self):
        jrprint('JrMindMap debug nodes:\n')
        for id, node in self.nodes.items():
            jrprint(' Node {} ({})'.format(node['id'], node['props']['mtype']))
            for linkFrom in node['from']:
                nodeFrom = linkFrom['from']
                jrprint('    from node {} ({}) via {}'.format(nodeFrom['id'], nodeFrom['props']['mtype'], linkFrom['props']['mtype']))
            for linkTo in node['to']:
                nodeTo = linkTo['to']
                jrprint('    to node {} ({}) via {}'.format(nodeTo['id'], nodeTo['props']['mtype'], linkTo['props']['mtype']))
        jrprint('\n\n')
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def findNodeById(self, id):
        if (id in self.nodes):
            return self.nodes[id]
        return None
    
    def addNode(self, node):
        nodeId = node['id']
        self.nodes[nodeId] = node
    
    def addLink(self, link):
        fromNode = link['from']
        toNode = link['to']
        fromNode['to'].append(link)
        toNode['from'].append(link)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def createNode(self, id, props):
        node = {'id': id, 'from': [], 'to': [], 'props': props}
        return node


    def createLink(self, fromNode, toNode, props):
        link = {'from': fromNode, 'to': toNode, 'props': props}
        return link
# ---------------------------------------------------------------------------
            


# ---------------------------------------------------------------------------
    def renderToDotText(self):
        self.buildGraphViz()
        return self.dot.source


    def renderToDotFile(self, outFilePath, encoding='utf-8'):
        dotText = self.renderToDotText()
        with open(outFilePath, 'w', encoding=encoding) as outfile:
            outfile.write(dotText)


    def renderToDotImageFile(self, outFilePath):
        jrprint('Drawing graphizualization to: {}'.format(outFilePath))
        self.buildGraphViz()
        self.dot.render(outFilePath)
# ---------------------------------------------------------------------------
 

# ---------------------------------------------------------------------------
    def cleanLabel(self, text):
        matches = re.match(r'([^\(]*)\(.*contd\.', text)
        if (matches is not None):
            text = matches[1].strip() + ' contd.'
            # TEST for inline short label
            text = 'cont.'
        text = text.strip()
        return text
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def buildGraphViz(self):
        jrprint('Building graphiviz structure...')

        # main graph
        dot = graphviz.Digraph(comment='Story')
        dot.attr(rankdir='LR', size='8.5, 11')

        # add all nodes
        for id, node in self.nodes.items():
            # add nodes
            nodeId = node['id']
            label = node['props']['label'] if ('label' in node['props']) else nodeId
            if (label is None):
                label = nodeId
            else:
                label = self.cleanLabel(label)
            #
            mtype = node['props']['mtype']

            # shapes see https://graphviz.org/doc/info/shapes.html
            color = 'black'
            if (mtype=='concept'):
                shape='ellipse'
            elif ('inline' in mtype):
                shape='rectangle'
                color = 'green'
            elif (mtype=='person'):
                shape = 'hexagon'
            elif (mtype=='yellow'):
                shape = 'house'
            else:
                shape = 'rectangle'
            #
            dot.node(nodeId, label, shape=shape, color=color)

        # add all links
        for id, node in self.nodes.items():
            nodeId = node['id']
            for link in node['to']:
                toNode = link['to']
                toNodeId = toNode['id']
                linkType = link['props']['mtype']
                dotEdgeLabel = linkType
                dot.edge(nodeId, toNodeId, dotEdgeLabel)

        # store it
        self.dot = dot
# ---------------------------------------------------------------------------
 

