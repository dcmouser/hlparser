# helper class for hl parser tool

from lib.jr import jrfuncs
from lib.jr import jroptions
from lib.jr.jrfuncs import jrprint
from lib.jr.jrfuncs import jrException

from lib.jr.hlmarkdown import HlMarkdown

# python modules
import re
import csv
import os
import pathlib
from collections import OrderedDict
import json
import random
import argparse






# ---------------------------------------------------------------------------
class HlParser:

    def __init__(self, optionsDirPath, overrideOptions={}):
        # load options
        self.jroptions = None
        self.jroptionsWorkingDir = None
        self.storyFileList = []
        self.headBlocks = []
        self.leads = {}
        self.unusedLeads = []
        self.warnings = []
        self.dynamicLeadMap = {}
        self.leadSections = {}
        self.tagMap = {}
        self.tagLabelsAvailable = [] #list(map(chr, range(ord('A'), ord('Z')+1)))
        self.tagLabelStage = 0
        random.shuffle(self.tagLabelsAvailable)
        #
        self.argDefs = {
            'header': {
                'named': ['id', 'label', 'existing', 'ignore', 'section', 'type', 'warning', 'autoid', 'render', 'sort'],
                'positional': ['id', 'label'],
                'required': []
            },
            'tag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'lead': {'named': ['leadId'], 'positional': ['leadId'], 'required': ['leadId']},
            'options': {'named': ['json'], 'positional': ['json'], 'required': ['json']},
            'jumplead': {},
            'gaintag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'havetag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'missingtag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'endjump': {},
            'insertlead': {'named': ['leadId'], 'positional': ['leadId'], 'required': ['leadId']},
        }
        #
        self.doLoadAllOptions(optionsDirPath, overrideOptions)
        #
        renderOptions = self.getOptionValThrowException('renderOptions')
        markdownOptions = renderOptions['markdown']
        self.hlMarkdown = HlMarkdown(markdownOptions)
        #
        self.loadUnusedLeadsFromFile(self.getOptionValThrowException('unusedLeadFile'))
# ---------------------------------------------------------------------------
        



# ---------------------------------------------------------------------------
    def runAll(self):
        self.loadStoryFilesIntoBlocks()
        #
        self.processHeadBlocks()
        self.saveLeads()
        self.renderLeads()
        #
        self.debug()
        self.reportWarnings()
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
    def processCommandline(self, appName, appInfo):
        parser = argparse.ArgumentParser(prog = appName, description = appInfo)
        parser.add_argument('-w', '--workingdir', required=False)
        args = parser.parse_args()
        #
        workingdir = args.workingdir
        if (workingdir):
            self.mergeOverrideOptions({'workingdir': workingdir})
        #
        self.runAll()
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
    def doLoadAllOptions(self, optionsDirPath, overrideOptions):
        self.loadOptions(optionsDirPath)
        # apply overrides (which may include a workingdir override)
        self.mergeOverrideOptions(overrideOptions)
        # load workingdir options
        workingDirPath = self.getBaseOptionValThrowException('workingdir')
        self.loadWorkingDirOptions(workingDirPath)


    def loadOptions(self, optionsDirPath):
        # create jroptions helper
        self.jroptions = jroptions.JrOptions(optionsDirPath)
        jrprint('Loading options from {}..'.format(optionsDirPath))
        # load basics
        self.jroptions.loadOptionsFile('options', True, True)
        self.jroptions.loadOptionsFile('private', True, False)

    def saveOptions(self):
        jrprint('Saving options back to original option data files..')
        self.jroptions.saveOptionsFiles(True)

    def mergeOverrideOptions(self, overrideOptions):
        if (len(overrideOptions)>0):
            jrprint('Merging options: {}.'.format(overrideOptions))
            self.jroptions.mergeRawDataForKey('options', overrideOptions)


    def loadWorkingDirOptions(self, optionsDirPath):
        # create jroptions helper
        self.jroptionsWorkingDir = jroptions.JrOptions(optionsDirPath)
        if (optionsDirPath==None):
            return
        jrprint('Loading workingdir options from {}..'.format(optionsDirPath))
        # load basics
        self.jroptionsWorkingDir.loadOptionsFile('options', True, False)
        self.jroptionsWorkingDir.loadOptionsFile('private', True, False)

    def getOptionValThrowException(self, keyName):
        # try to get from working dir options, fall back to base options
        val = self.getWorkingOptionVal(keyName, None)
        if (val==None):
            val = self.getBaseOptionVal(keyName, None)
        if (val==None):
            raise Exception('Key "{}" not found in options.'.format(keyName))
        return val
    
    def getOptionVal(self, keyName, defaultVal):
        # try to get from working dir options, fall back to base options
        val = self.getWorkingOptionVal(keyName, None)
        if (val==None):
            val = self.getBaseOptionVal(keyName, None)
        if (val==None):
            val = defaultVal
        return val
    #
    def getBaseOptionValThrowException(self, keyName):
        return self.jroptions.getKeyValThrowException('options', keyName)
    def getWorkingOptionValThrowException(self, keyName):
        return self.getKeyValThrowException.getKeyVal('options', keyName)
    def getBaseOptionVal(self, keyName, defaultVal):
        return self.jroptions.getKeyVal('options', keyName, defaultVal)
    def getWorkingOptionVal(self, keyName, defaultVal):
        return self.jroptionsWorkingDir.getKeyVal('options', keyName, defaultVal)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def loadStoryFilesIntoBlocks(self):
        jrprint('Scanning for and loading lead files..')
        storyDirectoriesList = self.getOptionValThrowException("storyDirectories")
        for storyDir in storyDirectoriesList:
            self.findStoryFilesFromDir(storyDir)
        # ok now with each lead file we found, process it
        for storyFilePath in self.storyFileList:
            self.loadStoryFileIntoBlocks(storyFilePath)


    def findStoryFilesFromDir(self, directoryPathOrig):
        directoryPath = self.resolveTemplateVars(directoryPathOrig)
        #
        if (directoryPath != directoryPathOrig):
            jrprint("Scanning for story files in {} ({}):".format(directoryPath, directoryPathOrig))
        else:
            jrprint("Scanning for story files in {}:".format(directoryPath))

        # recursive scan
        for (dirPath, dirNames, fileNames) in os.walk(directoryPath):
            for fileName in fileNames:
                fileNameLower = fileName.lower()
                baseName = pathlib.Path(fileName).stem
                dirPathLink = dirPath
                fileFinishedPath = dirPathLink + '/' + fileName
                if (fileNameLower.endswith('.txt')):
                    jrprint('Adding file "{}" to lead queue.'.format(fileFinishedPath, baseName))
                    self.storyFileList.append(fileFinishedPath)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def loadStoryFileIntoBlocks(self, filePath):
        jrprint('Loading story file: "{}"'.format(filePath))
        encoding = self.getOptionValThrowException('storyFileEncoding')
        fileText = jrfuncs.loadTxtFromFile(filePath, True, encoding)
        # parse text file into blocks
        sourceLabel = 'FILE "{}"'.format(filePath)
        self.parseStoryTextIntoBlocks(fileText, sourceLabel)



    def parseStoryTextIntoBlocks(self, text, sourceLabel):
        headBlock = None
        curTextBlock = None
        curText = ''
        inSingleLineComment = False
        inSingleLineHead = False
        inBlockCommentDepth = 0
        inCodeBlackDepth = 0
        inRaw = False
        lineNumber = 0
        posOnLine = -1
        cprev = ''
        #
        validShortCodeStartCharacterList = 'abcdefghijklmnopqrstuvwxyz'
        #
        # add newline to text to make sure we handle end of last line
        text = text + '\n'
        textlen = len(text)
        #
        i = -1
        while (True):
            i += 1
            if (i>=textlen):
                break
            # handle end of previous line
            if (cprev == '\n'):
                # last character was end of line
                posOnLine = 0
                lineNumber += 1
            else:
                posOnLine += 1
            #  get this and next char
            c = text[i]
            cprev = c
            if (i<textlen-1):
                cnext = text[i+1]
            else:
                cnext = ''
            #


            if (inRaw):
                # grabbing everything until we get a valid next head block
                if (c=='#') and (cnext==' ') and (posOnLine==0):
                    # we got something new
                    inRaw = False
                else:              
                    # raw text glob
                    if (curTextBlock is None):
                        # create new text block
                        curTextBlock = self.makeBlockText(sourceLabel, lineNumber)
                        self.addChildBlock(headBlock, curTextBlock)
                    # add character to textblock
                    curTextBlock['text'] += c
                    continue

            if (c=='\n'):
                if (inSingleLineHead):
                    # process the single line head
                    inSingleLineHead = False
                    curText = curText.strip()
                    headBlock = self.makeBlockHeader(curText, sourceLabel, lineNumber, 'lead')
                    self.addHeadBlock(headBlock)
                    if ('raw' in headBlock['properties']) and (headBlock['properties']['raw']==True):
                        # raw mode grabs EVERYTHING as text until the next header
                        inRaw = True
                    # clear current text
                    curText = ''
                    continue
                if (inSingleLineComment):
                    # single line comments end at end of line
                    inSingleLineComment = False
                    # should we eat the \n part of previous text?
                    if (False):
                        continue




            # warnings
            if (c=='#') and (cnext==' ') and (posOnLine==1) and ((inCodeBlackDepth>0) ):
                jrprint('WARNING: got a header inside a code block; source: {} line: {} pos: {}'.format(sourceLabel, lineNumber, posOnLine))
            if (c=='#') and (cnext==' ') and (posOnLine==1) and ((inBlockCommentDepth>0) ):
                jrprint('WARNING: got a header inside a comment block; source: {} line: {} pos: {}'.format(sourceLabel, lineNumber, posOnLine))

            #
            if (c=='/') and (cnext=='*'):
                # blockComment start
                i+=1
                inBlockCommentDepth += 1
                if (inBlockCommentDepth==1):
                    # clear current text block
                    curTextBlock = None
                continue
            if (c=='*') and (cnext=='/'):
                # blockComment end
                i+=1
                inBlockCommentDepth -= 1
                if (inBlockCommentDepth<0):
                    self.raiseParseException('End of comment block "*/" found without matching start.', i, posOnLine, lineNumber, text, sourceLabel)
                continue
            if (inBlockCommentDepth>0):
                # in multi-line comment, ignore it
                continue
            #
            if (inSingleLineComment):
                # we are on a comment line, just ignore it
                continue
            if (c=='/') and (cnext=='/'):
                # single comment line start
                inSingleLineComment = True
                continue

            #
            if (c=='{') and (not inSingleLineHead):
                # code block start
                inCodeBlackDepth += 1
                if (inCodeBlackDepth==1):
                    # outer code block { does not capture
                    # clear current text block
                    curTextBlock = None
                    codeBlockStartLineNumber = lineNumber
                    continue
            if (c=='}') and (not inSingleLineHead):
                # code block end
                inCodeBlackDepth -= 1
                if (inCodeBlackDepth<0):
                    self.raiseParseException('End of code block "}" found without matching start.', i, posOnLine, lineNumber, text, sourceLabel)
                if (inCodeBlackDepth==0):
                    # close of code block
                    curText = curText.strip()
                    block = self.makeBlockCode(curText, sourceLabel, codeBlockStartLineNumber, False)
                    self.addChildBlock(headBlock, block)
                    # clear current text to prepare for next block section
                    curText = ''
                    # out code block } does not capture
                    continue
            #
            if (c=='$') and (cnext in validShortCodeStartCharacterList) and (not inSingleLineHead) and (inCodeBlackDepth==0):
                # got a shorthand code line (does not use {} but rather of the form $func(params))
                # just consume it all now
                [shortCodeText, resumePos] = self.consumeShortCodeFromText(text, sourceLabel, lineNumber, posOnLine, i+1)
                if (resumePos==-1):
                    # false alarm no shortcode
                    pass
                else:
                    # got some shortcode
                    shortCodeText = shortCodeText.strip()
                    block = self.makeBlockCode(shortCodeText, sourceLabel, lineNumber, True)
                    self.addChildBlock(headBlock, block)
                    # clear current text to prepare for next block section
                    curText = ''
                    curTextBlock = None
                    i = resumePos-1
                    continue
            #
            if (c=='#') and (cnext==' ') and (posOnLine==0) and (not inSingleLineHead) and (inCodeBlackDepth==0):
                # "#" at start of line followed by space means we have a header
                # skip next char
                i+=1
                inSingleLineHead = True
                # clear current text block
                curTextBlock = None
                continue
            #
            if (not inSingleLineHead) and (inCodeBlackDepth==0) and (not inSingleLineComment) and (inBlockCommentDepth==0):
                # we are in a text block
                if (curTextBlock is None):
                    # create new text block
                    curTextBlock = self.makeBlockText(sourceLabel, lineNumber)
                    self.addChildBlock(headBlock, curTextBlock)
                # add character to textblock
                curTextBlock['text'] += c
            else:
                # accumulating text for later block use
                # add c to current text (be in codeblock, or text, or header)
                curText += c

        # make sure didnt end in comments, etc.
        if (inSingleLineHead):
            self.raiseParseException('Unexpected end of text while parsing "#" header.', i, posOnLine, lineNumber, text, sourceLabel)
        if (inCodeBlackDepth>0):
            self.raiseParseException('Unexpected end of text while inside code block.', i, posOnLine, lineNumber, text, sourceLabel)
        if (inBlockCommentDepth>0):
            self.raiseParseException('Unexpected end of text while inside comment block.', i, posOnLine, lineNumber, text, sourceLabel)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def raiseParseException(msg, posInText, posOnLine, lineNumber, text, sourceLabel):
        msgExpanded = 'Parsing error: {} in {} at line {} pos {}.'.format(msg, sourceLabel, lineNumber, posOnLine)
        jrprint(msgExpanded)
        raise Exception(msgExpanded)
# ---------------------------------------------------------------------------































































# ---------------------------------------------------------------------------
    def addHeadBlock(self, headBlock):
        self.headBlocks.append(headBlock)

    def addChildBlock(self, headBlock, block):
        if (headBlock is None):
            self.raiseBlockException(block, 0, 'Child block ({}) specified but no previous parent headblock found.'.format(block['type']))

        # add as child block
        if ('blocks' not in headBlock):
            headBlock['blocks'] = []
        headBlock['blocks'].append(block)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def makeBlockEndFile(self, sourceLabel, lineNumber):
        block = self.makeBlock(sourceLabel, lineNumber, 'eof')
        return block

    def makeBlockText(self, sourceLabel, lineNumber):
        block = self.makeBlock(sourceLabel, lineNumber, 'text')
        return block

    def makeBlockCode(self, codeText, sourceLabel, lineNumber, embeddedShortCode):
        block = self.makeBlock(sourceLabel, lineNumber, 'code')
        block['text'] = codeText
        block['properties']['embeddedShortCode'] = embeddedShortCode
        return block

    def makeBlock(self, sourceLabel, lineNumber, blockType):
        # create it
        block = {}
        block['sourceLabel'] = sourceLabel
        block['lineNumber'] = lineNumber
        block['type'] = blockType
        block['text'] = ''
        block['properties'] = {}
        # return it
        return block
# ---------------------------------------------------------------------------
    

# ---------------------------------------------------------------------------
    def makeBlockHeader(self, headerText, sourceLabel, lineNumber, defaultHeaderType):
        #
        block = self.makeBlock(sourceLabel, lineNumber, 'header')

        # parse the header
        # ATTN: this needs to be recoded to not use regex and to support quotes labels that can contain ()
        # this checks for things that look like:
        #   ID STRING
        #   ID STRING: ID LABEL HERE
        #   ID STRING (extra options here)
        #   ID STRING: ID LABEL HERE (extra options here)
        #   ID STRING: (extra options here)

        # manual parse
        pos = 0
        [id, pos, nextc] = self.parseConsumeFunctionCallArgNext(block, headerText, pos, [':','(', ''])
        if (nextc==':'):
            [label, pos, nextc] = self.parseConsumeFunctionCallArgNext(block, headerText, pos+1, ['(', ''])
        else:
            label = ''
        if (nextc=='('):
            argString = headerText[pos:]
        else:
            argString = ''

        
        linePos = 0
        # args first taken from any explicit ly passed
        if (argString!=''):
            [properties, pos] = self.parseFuncArgs('header', argString, sourceLabel, lineNumber, linePos)
        else:
            properties = {}

        # now set id and label
        if ('id' not in properties):
            properties['id'] = id
        else:
            id = properties['id']

        # label
        if ('label' not in properties):
            properties['label'] = label

        # default header subtype arg
        if ('type' not in properties):
            properties['type'] = defaultHeaderType

        # special ids
        if (id=='options'):
            properties['type']= 'options'
            properties['raw'] = True
        if (id=='comments'):
            properties['type']= 'comments'
            properties['raw'] = True

        # store properties
        block['properties'] = properties

        return block
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def consumeShortCodeFromText(self, text, sourceLabel, lineNumber, posOnLine, textPos):
        # return [shortCodeText, resumePos]
        remainderText = text[textPos:]
        matches = re.match(r'^([a-z][A-Za-z0-9_]*)(\(.*)$', remainderText, re.MULTILINE)
        if (matches is None):
            # bad
            return ['',-1]
        funcName = matches[1]
        argText = matches[2]
        [argVals, afterPos] = self.parseFuncArgs(funcName, argText, sourceLabel, lineNumber, posOnLine)
        parsedParamLen = afterPos+1
        codeFullText = funcName + argText[0:parsedParamLen-1]
        returnPos = textPos + len(funcName) + parsedParamLen - 1
        return [codeFullText, returnPos]
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def parseFuncArgs(self, funcName, text, sourceLabel, lineNumber, posOnLine):
        # expect comma separated list of possibly named arguments
        argVals = {}

        # now grab inside ()
        # this can be TRICKY because of nesting quoutes escaped characters etc
        #return tuple [args,pos] where pos is position of the ) at the end

        # struct for reporting errors
        block = {'sourceLabel': sourceLabel, 'lineNumber': lineNumber}

        # what args do we expect for this function
        argDefs = self.funcArgDef(funcName)
        positionalArgs = argDefs['positional'] if ('positional' in argDefs) else []
        namedArgs = argDefs['named'] if ('named' in argDefs) else []
        requiredArgs = argDefs['required'] if ('required' in argDefs) else []


        # confirm we start with ()
        pos = 0
        if (text[pos]!='('):
            self.raiseBlockExceptionAtPos(block, pos, 'Expected function name')
            return False 

        # iterate through all comma separated params
        isDone = False
        argIndex = -1
        pos += 1
        while (not isDone):
            ePos = pos
            [key, val, pos, isDone] = self.parseConsumeFunctionCallArgPairNext(block, text, pos)
            # ATTN: 12/26/23 new to add code here to ensure its legal parameter (positional or named)
            # parsed a paramPair val
            # add it
            argIndex += 1
            if (val=='') and (key is None):
                # no arg available
                if (not isDone):
                    self.raiseBlockExceptionAtPos(block, posOnLine+ePos, 'Got blank arg but not done with args ({}) passed to function {}.'.format(argIndex, funcName))
                    return False 
            elif (key is None):
                # its positional; convert to argdef defined prop name
                if (len(positionalArgs)<=argIndex):
                    self.raiseBlockExceptionAtPos(block, posOnLine+ePos, 'Too many args ({}) passed to function {}.'.format(argIndex, funcName))
                    return False 
                propName = positionalArgs[argIndex]
                argVals[propName] = val
            else:
                # use the key
                if (key not in namedArgs):
                    self.raiseBlockExceptionAtPos(block, posOnLine+ePos, 'Unknown named parameter ({}) passed to function {}.'.format(key, funcName))
                    return False 
                argVals[key] = val

        # ATTN: 12/26/23 need to add code here to make sure all REQUIRED params are passed
        for key in requiredArgs:
            if (key not in argVals):
                self.raiseBlockExceptionAtPos(block, posOnLine, 'Missing required arg({}) passed to function call {}.'.format(key, funcName))
                return False   

        # return parsed argVals and pos after end of parsing which should be ')' location
        return [argVals, pos]
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def parseConsumeFunctionCallArgPairNext(self, block, blockText, startPos):
        key = None
        pos =  startPos
        stopCharList = [',' , '=' , ')']
        #

        # get first val
        [val, pos, nextc] = self.parseConsumeFunctionCallArgNext(block, blockText, pos, stopCharList)

        blockTextLen = len(blockText)
        #c = blockText[pos]
        c = nextc
        if (c == '='):
            # we have a named param
            key = val
            pos += 1
            [val, pos, nextc] = self.parseConsumeFunctionCallArgNext(block, blockText, pos, stopCharList)
            #c = blockText[pos]
            c = nextc
        if (c==')'):
            isDone = True
        elif (c==','):
            # more params left
            isDone = False
        else:
            # error syntax
            self.raiseBlockExceptionAtPos(block, startPos, 'Syntax error while parsing function call parameters')
            return False 
        # advance over comma )
        pos += 1

        # advance following whitespace? i dont think we want to
        if (False):
            textlen = len(blockText)
            while (pos<textlen) and (blockText[pos].isspace()):
                pos += 1
        # return
        return [key, val, pos, isDone]



    def parseConsumeFunctionCallArgNext(self, block, blockText, startPos, stopCharList):
        # parse next comma separate val or var=val
        wrapperCharList = ['"', "'", '{']
        textlen = len(blockText)

        # go to first non-space character
        pos = startPos
        while (blockText[pos].isspace()) and (pos<textlen):
            pos += 1
        if (pos>=textlen):
            self.raiseBlockExceptionAtPos(block, startPos, 'Unexpected end inside function call parameters')
            return False 

        # skip comments
        pos = self.skipComments(block, blockText, pos)
        extractedText = ''

        # ok now see if we have an ENCLOSING character
        c = blockText[pos]
        openingChar = ''
        keepFinalClose = False
        if (c in wrapperCharList):
            # yes we have an enclosing
            if (c=='{'):
                openingChar = '{'
                closingChar = '}'
                keepFinalClose = True
                extractedText = c
            elif (c=='('):
                openingChar = '('
                closingChar = ')'
                keepFinalClose = True
                extractedText = c
            else:
                openingChar = ''
                closingChar = c
                keepFinalClose = False
            wrapperDepth = 1
            # advance inside
            pos += 1
        else:
            closingChar = None
            wrapperDepth = 0

        # loop
        wasWrapped = (wrapperDepth>0)
        startContentPos = pos
        inEscapeNextChar = False
        expectingEnd = False
        while (pos<textlen):
            # skip comments
            c = blockText[pos]
            if (inEscapeNextChar):
                # this character is escaped
                extractedText += jrfuncs.escapedCharacterConvert(c)
                inEscapeNextChar = False
            else:
                # skip comments
                if (wrapperDepth==0) or (True):
                    # do we want to do this even if in wrapper? YES for now (note this is different from most programming languages)
                    pos = self.skipComments(block, blockText, pos)
                    c = blockText[pos]

                if (wrapperDepth>0):
                    # inside wrapper the only thing we care about is close of wrapper
                    if (c=='\\'):
                        # escape
                        inEscapeNextChar = True
                        pass
                    elif (c==closingChar):
                        # got close of wrapper
                        wrapperDepth -= 1
                        if (wrapperDepth==0):
                            expectingEnd = True
                        if (keepFinalClose) or (wrapperDepth>0):
                            extractedText += c
                        if (wrapperDepth<0):
                            self.raiseBlockExceptionAtPos(block, startContentPos, 'Syntax error while parsing function call parameters; unexpected unbalanced wrapper close symbol')
                            return False 
                    elif (c==openingChar):
                        wrapperDepth += 1
                        extractedText += c
                    else:
                        # stay in wrapper
                        extractedText += c
                        pass
                else:
                    # not in wrapper
                    #
                    if (c in stopCharList):
                        # this ends our parse since we are not in wrapper
                        break
                    elif (expectingEnd) and (not c.isspace()):
                        # error since we thought we were done
                        self.raiseBlockExceptionAtPos(block, startContentPos, 'Syntax error while parsing function call parameters; expecting end but there was something else')
                        return False 
                    # characters allowed
                    elif (c=='\\'):
                        # escape
                        inEscapeNextChar = True
                        pass
                    else:
                        # just a normal character
                        extractedText += c
            # advance to next char
            pos += 1

        if (inEscapeNextChar):
            self.raiseBlockExceptionAtPos(block, startContentPos, 'Syntax error (unexpected end of line while in escape char) while parsing function call parameters')
            return False 
        if (wrapperDepth>0):
            self.raiseBlockExceptionAtPos(block, startContentPos, 'Syntax error (unexpected end of line while in wrapper quotes/brackets/etc) while parsing function call parameters')
            return False 

        if (pos>=textlen):
            if (not '' in stopCharList):
                self.raiseBlockExceptionAtPos(block, startContentPos, 'Syntax error (unexpected end of line) while parsing function call parameters')
                return False 
            else:
                # last char '' to mean end of string
                c = ''

        if (not wasWrapped):
            # trim spaces front and back if not in wrapper
            extractedText = extractedText.strip()
        #    
        return [extractedText, pos, c]
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def parseFunctionCallAndArgs(self, block, text):
        # 
        sourceLabel = block['sourceLabel']
        lineNumber = block['lineNumber']
        linePos = 0
        pos = 0
        #
        [funcName, pos, nextc] = self.parseConsumeFunctionCallArgNext(block, text, pos, ['(', ''])
        if (nextc=='('):
            argString = text[pos:]
        else:
            argString = ''

        # args first taken from any explicit ly passed
        if (argString!=''):
            [properties, pos] = self.parseFuncArgs(funcName, argString, sourceLabel, lineNumber, linePos)
        else:
            properties = {}

        return [funcName, properties, pos]
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def skipComments(self, block, text, pos):
        startPos = pos
        textlen = len(text)
        blockCommentDepth = 0

        while (pos<textlen):
            if (text[pos]=='/') and (text[pos+1]=='/'):
                # skip till end of line
                pos += 2
                while (pos<textlen) and (text[pos-1]!='\n'):
                    pos += 1
            elif (text[pos]=='/') and (text[pos+1]=='*'):
                blockCommentDepth += 1
                pos += 2
                while (pos<textlen-1):
                    if (text[pos]=='*') and (text[pos+1]=='/'):
                        blockCommentDepth -= 1
                        pos += 2
                        if (blockCommentDepth==0):
                            break
                        if (blockCommentDepth<0):
                            self.raiseBlockExceptionAtPos(block, pos-2, 'Syntax error close block comment without start */ unterminated.')
                            return False
                    elif (text[pos]=='/') and (text[pos+1]=='*'):
                        # nested block comment
                        blockCommentDepth += 1
                        pos += 2
                    else:
                        # still in block continue
                        pos += 1
            else:
                break

        if (blockCommentDepth!=0):
            self.raiseBlockExceptionAtPos(block, startPos, 'Syntax error nested block comments /* */ unterminated.')
            return False

        return pos
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def isValidFuncName(self, name):
        if (' ' in name):
            return False
        if (name=='lead'):
            return True
        # unknown
        return False
# ---------------------------------------------------------------------------



    







































# ---------------------------------------------------------------------------
    def processHeadBlocks(self):
        # first we make a pass for EARLY stage processing
        # we need to do this in multiple stages because we do NOT want to fully process a lead if it is overwritten by another later
        jrprint('Parsing {} head blocks..'.format(len(self.headBlocks)))
        for block in self.headBlocks:
            self.processHeadBlock(block)

        # now process leads
        jrprint('Processing {} leads..'.format(len(self.leads)))
        leadkeys = list(self.leads.keys())
        for leadId in leadkeys:
            lead = self.leads[leadId]
            self.processLead(lead)




    def processHeadBlock(self, block):
        # there's THREE things that happen when parsing a block.
        # 1) we can parse functions that set PROPERTIES for the block (like identify it as a lead, and set its LEAD ID etc)
        # 2) we can parse functions that do replacements inside the text of the block
        # 3) we can parse functions that create other data (more leads, etc)
        #jrprint('Processing a block..')

        # now post-process it based on type
        properties = block['properties']
        blockType = properties['type']
        if (blockType is None):
            self.raiseBlockException(block, 0, 'Block encountered but of unknown type.')

        if (blockType=='lead'):
            # it's a lead type of block, our most common
            id = properties['id']
            existingLead = self.findLeadById(id)
            if (existingLead is not None):
                existingLegalValues = ['defer', 'overwrite']
                errorMsg = None
                # already have a lead of with this id
                existingBehaviorNew = properties['existing'] if ('existing' in properties) else None
                propertiesPrior = existingLead['properties']
                existingBehaviorPrior = propertiesPrior['existing'] if ('existing' in propertiesPrior) else None
                # ok now throw an error if we get conflicting instructions
                if (existingBehaviorNew is None) and (existingBehaviorPrior is None):
                    # no instructions given what to do
                    errorMsg = 'The "existing" directive was not found in either lead, and must be specified on one or both leads [defer|overwrite]'
                elif ((existingBehaviorNew =='overwrite') or (existingBehaviorNew is None)) and ((existingBehaviorPrior is None) or (existingBehaviorPrior=='defer')):
                    # this is fine, we overwrite
                    existingBehaviorNew = 'overwrite'
                elif ((existingBehaviorNew == 'defer') or (existingBehaviorNew is None)) and ((existingBehaviorPrior is None) or (existingBehaviorPrior=='overwrite')):
                    # this is fine, we defer
                    existingBehaviorNew = 'defer'
                elif (existingBehaviorNew == 'defer') and (existingBehaviorPrior=='defer'):
                    # this is fine, we defer; neither care
                    existingBehaviorNew = 'defer'
                elif (existingBehaviorNew == 'overwrite') and (existingBehaviorPrior=='overwrite'):
                    # this is problem, both want to dominate
                    errorMsg = 'The "existing" directive was found in both leads and conflicts (both want "overwrite"); one should be set to "defer"'
                else:
                    # not understood
                    errorMsg = ''
                    if (existingBehaviorNew not in existingLegalValues):
                        errorMsg += 'Uknown value for "existing" directive in new lead (). '.format(existingBehaviorNew)
                    if (existingBehaviorPrior not in existingLegalValues):
                        errorMsg += 'Uknown value for "existing" directive in prior lead (). '.format(existingBehaviorNew)
                #
                if (errorMsg is not None):
                    # we have a conflict error
                    errorMsg += ' Prior lead with same id found in {} around line #{}'.format(existingLead['sourceLabel'], existingLead['lineNumber']+1)
                    self.raiseBlockException(block, 0, errorMsg)
                #
                if (existingBehaviorNew == 'defer'):
                    # there is an existing lead with this id and we are set to defer, so we dont add
                    warningMsg = 'WARNING: New lead with duplicate id({}) is being ignored because lead directive set to existing=defer; Prior lead with same id found in {} around line #{}.'.format(id, existingLead['sourceLabel'], existingLead['lineNumber']+1)
                    jrprint('WARNING: ' + warningMsg)
                    return
            else:
                # no other lead with this id so no conflict
                pass

            ignoreFlag = jrfuncs.getDictValueFromTrueFalse(properties, 'ignore', False)
            if (ignoreFlag):
                warningMsg = 'WARNING: Lead with id="{}" is being ignored because ignore=true in lead directive; lead is from {} around line #{}'.format(id, block['sourceLabel'], block['lineNumber']+1)
                jrprint('WARNING: ' + warningMsg)
                return

            # block text -- ATTN: we now do this in a second PASS
            blockText= ''

            # warnings
            warningVal = jrfuncs.getDictValueOrDefault(properties, 'warning', None)
            if (warningVal is not None):
                msg = 'Manual warning set for lead "{}": "{}" .... from {} around line #{}'.format(id, warningVal, block['sourceLabel'], block['lineNumber']+1)
                self.addWarning(msg)

            # render id
            autoid = jrfuncs.getDictValueFromTrueFalse(properties, 'autoid', False)
            if (autoid):
                # assign a free leads id
                renderId = self.assignDynamicLeadId(id, block)
                properties['renderId'] = renderId
            else:
                renderId = id
            properties['renderId'] = renderId

            # store section name in properties
            properties['sectionName'] = self.makeSectionNameForHeadBlock(block, renderId)

            # ok ADD the new lead by copying values from block
            lead = {'block': block, 'properties': properties, 'text': blockText, 'sourceLabel': block['sourceLabel'], 'lineNumber': block['lineNumber']}
            self.storeLeadId(id, lead)

        elif (blockType=='options'):
            # special options, just execute; do it here early
            self.processOptionsBlock(block)

        elif (blockType=='comments'):
            # do nothing
            pass

        elif (blockType=='ignore'):
            # just a way to say ignore this block, comments, etc
            warningMsg = 'WARNING: Block is being ignored because blocktype={}; from {} around line #{}'.format(blockType, block['sourceLabel'], block['lineNumber']+1)
            jrprint('WARNING: ' + warningMsg)
            return
        else:
            # something OTHER than a lead
            raise Exception('Unsupported block type: "{}"'.format(blockType))
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
    def processOptionsBlock(self, block):
        jsonOptionString = self.childRawBlockText(block)
        jsonOptions = json.loads(jsonOptionString)
        # set the WORKINGDIR options
        self.jroptionsWorkingDir.mergeRawDataForKey('options', jsonOptions)
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
    def makeSectionNameForHeadBlock(self, block, renderId):
        properties = block['properties']
        if ('section' in properties):
            # explicit section 
            return properties['section']

        blockType = properties['type']
        if (blockType == 'lead'):
            sectionName = 'Main.' + self.calcIdSection(renderId)
        else:
            sectionName = blockType
        #
        return sectionName
# ---------------------------------------------------------------------------






























































# ---------------------------------------------------------------------------
    def processLead(self, lead):
        leadProprties = lead['properties']
        jrprint('Processing lead "{}" from {} at line #{}'.format(leadProprties['id'], lead['sourceLabel'], lead['lineNumber']+1))
        #
        blockText = self.evaluateHeadBlockTextCode(lead)
        lead['text'] = blockText
# ---------------------------------------------------------------------------

























# ---------------------------------------------------------------------------
    def findLeadById(self, leadId):
        leadId = self.canonicalLeadId(leadId)
        if (leadId in self.leads):
            return self.leads[leadId]
        return None

    def storeLeadId(self, leadId, lead):
        leadId = self.canonicalLeadId(leadId)
        jrprint('Storing lead: {}.'.format(leadId))
        leadIndex = len(self.leads)
        lead['leadIndex'] = leadIndex
        self.leads[leadId] = lead

    def canonicalLeadId(self, id):
        # uppercase
        id = id.upper()
        # no spaces
        id = id.replace(' ','')
        # add space between letters and numbers (SHCD stye)
        matches = re.match(r'^([A-Za-z]+)\s*\-?\s*([0-9]+)$', id)
        if (matches is not None):
            id = matches[1] + ' ' + matches[2]
        #
        return id

    def calcIdSection(self, id):
        matches = re.match(r'^([A-Za-z0-9][A-Za-z0-9\.]+)\.(.*)$', id)
        if (matches is not None):
            # HL style id
            return matches[1].upper()
        matches = re.match(r'^([A-Za-z0-9\.]+)\s*\-\s*(.*)$', id)
        if (matches is not None):
            # HL style id
            return matches[1].upper()
        matches = re.match(r'^([A-Za-z]+)\s*\-?\s*([0-9]+)$', id)
        if (matches is not None):
            # shcd style id
            return matches[1].upper()
        matches = re.match(r'^([0-9]+)\s*\-?\s*([A-Za-z]+)$', id)
        if (matches is not None):
            # shcd style id reverse
            return matches[2].upper()
        # unknown
        return ''
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def saveLeads(self):
        saveDir = self.getOptionValThrowException('savedir')
        outFilePath = saveDir + '/leadsout.json'
        outFilePath = self.resolveTemplateVars(outFilePath)
        #
        # sort
        self.sortLeadsIntoSections()
        #
        jrprint('Saving leads to: {}'.format(outFilePath))
        encoding = self.getOptionValThrowException('storyFileEncoding')
        with open(outFilePath, 'w', encoding=encoding) as outfile:
            leadsJson = json.dumps(self.rootSection, indent=2)
            outfile.write(leadsJson)
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
    def sortLeadsIntoSections(self):
        self.rootSection = {}
        # ATTN: TODO - seed with some initial sections?
        optionSections = self.getOptionVal('sections', self.getDefaultSections())
        self.rootSection['sections'] = optionSections
        #self.createRootChildSection('Front', 'Front', '010')
        #self.createRootChildSection('Leads', 'Leads', '020')
        #self.createRootChildSection('Back', 'Back', '030')

        #
        for leadId, lead in self.leads.items():
            section = self.calcSectionForLead(lead)
            if ('leads' not in section):
                section['leads'] = {}
            section['leads'][leadId] = lead
        
        # now walk sections and sort leads and subsections
        if (len(self.rootSection)>0):
            self.sortSection(self.rootSection, 'index')


    def getDefaultSections(self):
        defaultSections = {
		"Briefings": {"label": "Briefings", "sort": "010"},
		"Main": {"label": "Main Leads", "sort": "050"},
		"End": {"label": "End", "sort": "100"},
	    }

        return defaultSections

    def createRootChildSection(self, id, label, sortOrder):
        parentSection = self.rootSection
        if ('sections' not in parentSection):
            # no children, add it
            parentSection['sections'] = {}
        if (id not in parentSection['sections']):
            parentSection['sections'][id] = {'label': label, 'sort': sortOrder}


    def sortSection(self, section, leadSort):
        if ('leadsort' in section):
            leadSort = section['leadsort']

        # sort leads
        if ('leads' in section):
            leads = section['leads']
            leadIds = list(leads.keys())
            # custom sort of lead ids
            leadIds.sort(key=lambda idStr: self.formatLeadIdForSorting(idStr, leads[idStr], leadSort))
            #
            leadSorted = {i: leads[i] for i in leadIds}
            section['leads'] = leadSorted

        # now recursively sort child sections
        if ('sections' in section):
            childSections = section['sections']
            for childid, child in childSections.items():
                self.sortSection(child, leadSort)
            # and sort keys for child sections
            section['sections'] = jrfuncs.sortDictByAKeyVal(section['sections'], 'sort')


    def calcSectionForLead(self, lead):
        # return the child section for this lead, creating the path to it if needed
        properties = lead['properties']
        sectionName = properties['sectionName']
        # split it into dot separated chain
        sectionNameParts = sectionName.split('.')
        section = self.rootSection
        for sectionNamePart in sectionNameParts:
            section = self.findCreateChildSection(section, sectionNamePart)
        return section
    

    def findCreateChildSection(self, parentSection, sectionNamePart):
        if ('sections' not in parentSection):
            # no children, add it
            parentSection['sections'] = {}
        if (sectionNamePart not in parentSection['sections']):
            sectionSortVal = jrfuncs.zeroPadNumbersAnywhereInStringAll(sectionNamePart, 6)
            parentSection['sections'][sectionNamePart] = {'label': sectionNamePart, 'sort': sectionSortVal}
        return parentSection['sections'][sectionNamePart]
# ---------------------------------------------------------------------------
































# ---------------------------------------------------------------------------
    def debug(self):
        jrprint('\n\n---------------------------\n')
        jrprint('Debugging hlParser:')
        jrprint('Base options: {}'.format(self.jroptions.getAllBlocks()))
        jrprint('Working dir options: {}'.format(self.jroptionsWorkingDir.getAllBlocks()))
        jrprint('Scan found {} lead files: {}.'.format(len(self.storyFileList), self.storyFileList))
        jrprint('Tag map:\n')
        jrprint(self.tagMap)
        if (False):
            jrprint('Headblocks:\n')
            for block in self.headBlocks:
                blockDebugText = self.calcDebugBlockText(block)
                jrprint(blockDebugText)
        jrprint('---------------------------\n')


    def calcDebugBlockText(self, block):
        # just create a debug text for the block
        optionSummarizeChildBlocks = True
        tempBlock = jrfuncs.deepCopyListDict(block)
        if (optionSummarizeChildBlocks):
            if ('blocks' in tempBlock):
                tempBlock['blocks'] = len(tempBlock['blocks'])
        debugText = json.dumps(tempBlock, indent=2)
        return debugText


    def reportWarnings(self):
        if (len(self.warnings)==0):
            jrprint('{} warnings.'.format(len(self.warnings)))
            return
        jrprint('{} warnings:'.format(len(self.warnings)))
        for index, warning in enumerate(self.warnings):
            jrprint('[{}]: {}'.format(index+1, warning))
        jrprint('\n')



    def addWarning(self, txt):
        self.warnings.append(txt)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def combineLinesToText(self, lines):
        lineText = ''
        for line in lines:
            lineText += line['text'] + '\n'
        lineText = lineText.strip()
        return lineText
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def loadUnusedLeadsFromFile(self, filePath):
        filePath = self.resolveTemplateVars(filePath)
        with open(filePath) as csvFile:
            csvReader = csv.DictReader(csvFile)
            for row in csvReader:
                self.unusedLeads.append(row)
        jrprint('{} unused leads read from "{}"'.format(len(self.unusedLeads), filePath))
        #print(self.unusedLeads)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def resolveTemplateVars(self, text):
        text = text.replace('$workingdir', self.getBaseOptionVal('workingdir', ''))
        text = text.replace('$basedir', self.getBaseOptionVal('basedir', ''))
        return text
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def raiseBlockException(self, block, lineNumber, message):
        if ('id' in block):
            blockIdInfo = '(id = "{}")'.format(block['id'])
        else:
            blockIdInfo = ''
        #
        msg = 'Exception encountered while processing block {} from {} around line #{}: {}'.format(blockIdInfo, block['sourceLabel'], block['lineNumber']+lineNumber+1, message)
        jrException(msg)
        raise Exception(msg)

    def raiseBlockExceptionAtPos(self, block, pos, message):
        # go from pos to line # and pos
        lineNumber = block['lineNumber']
        linePos = pos
        #

        msg = message + ' (at pos {}).'.format(linePos)
        self.raiseBlockException(block, lineNumber, msg)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def doShorthandParsingReplacements(self, shorthandParsingOptions, text):
        inText = text

        # no longer using these
        if (False):
            if ('simpleLeads' in shorthandParsingOptions) and (shorthandParsingOptions['simpleLeads']):
                regexPlaintextLead1 = re.compile(r'^\s*(\d+\-\d+)\s*$',re.IGNORECASE)
                text = regexPlaintextLead1.sub(r'$lead(\1)', text)

                regexPlaintextLead2 = re.compile(r'^\s*(\d+\-\d+)[\-\s]+(.*[^\s])\s*$',re.IGNORECASE)
                text = regexPlaintextLead2.sub(r'$lead(\1, "\2")', text)

        if (False) and (text != inText):
            jrprint('DEBUG: Shorthand line expanded from "{}" to: "{}".'.format(inText, text))

        return text
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def formatLeadIdForSorting(self, idStr, lead, leadSort):
        
        properties = lead['properties']
        if ('sort' in properties) and (properties['sort']!=''):
            val = properties['sort']
            if (val=='index'):
                val = str(lead['leadIndex'])
        else:
            # if there are numbers at start or end then we will sort by id
            if (leadSort=='index'):
                # no digits at start or end, so use ADD order
                val = str(lead['leadIndex'])
            elif (leadSort=='') or (leadSort=='alpha'):
                val = idStr
            else:
                raise Exception('Unknown sort value: {} near {} line {}.'.format(leadSort, lead['sourceLabel'], lead['lineNumber']))
        digitlen = 6
        return jrfuncs.zeroPadNumbersAnywhereInStringAll(val, digitlen)
        numericalLeadRegex = re.compile(r'^(\d+)\-(.*)$')
        matches = numericalLeadRegex.match(idStr)
        if (matches is not None):
            prefix = int(matches[1])
            sortKey = '{:0>4}-{}'.format(prefix, matches[2])
            print('in with "{}" out with "{}"'.format(idStr, sortKey))
            return sortKey
        # leave as is
        return idStr
# ---------------------------------------------------------------------------
    


# ---------------------------------------------------------------------------
    def funcArgDef(self, funcName):
        # return dictionary defining args expected from this function
        if (funcName in self.argDefs):
            return self.argDefs[funcName]
        raise Exception('Unknown function name in funcArgDef: {}.'.format(funcName))
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def assignDynamicLeadId(self, id, block):
        # use a lead id from our unused list and keep track of it
        if (id in self.dynamicLeadMap):
            self.raiseBlockException(block, 0, 'Duplicate DYNAMIC lead id "{}" found previously assigned to a dynamic id; needs to be unique.'.format(id))
        renderId = self.consumeUnusedLeadId()
        oldLead = self.findLeadById(renderId)
        if (oldLead is not None):
            self.raiseBlockException(block, 0, 'ERROR: unused lead returned an id ({}) that already exists in lead table ({} at {}) for DYNAMIC lead id "{}"'.format(renderId, oldLead['sourceLabel'], oldLead['lineNumber'], id))
        self.dynamicLeadMap[id] = renderId
        return renderId
    
    def consumeUnusedLeadId(self):
        unusedLeadRow = self.unusedLeads.pop()
        leadid = unusedLeadRow['lead']
        return leadid
# ---------------------------------------------------------------------------














































# ---------------------------------------------------------------------------
# ok here is our new code to evaluate blocks
    def childRawBlockText(self, headBlock):
        if ('blocks' not in headBlock):
            return ''
        
        # ATTN: test 12/30/23 just combine all text lines
        # ATTN: TODO handle code blocks and conditionals
        txt = ''
        childBlocks = headBlock['blocks']
        for block in childBlocks:
            blockType = block['type']
            if (blockType=='text'):
                txt += block['text']
            elif (blockType=='code'):
                txt += block['text']
            else:
                self.raiseBlockException(self, block, 0, 'Unknown block type "{}"'.format(blockType))

        # trim
        txt = txt.strip()

        return txt
# ---------------------------------------------------------------------------
    






# ---------------------------------------------------------------------------
# ok here is our new code to evaluate blocks
    def evaluateHeadBlockTextCode(self, lead):
        headBlock = lead['block']
        if ('blocks' not in headBlock):
            return ''
        
        # ATTN: test 12/30/23 just combine all text lines
        # ATTN: TODO handle code blocks and conditionals
        txt = ''
        childBlocks = headBlock['blocks']
        blockIndex = -1
        while (blockIndex<len(childBlocks)-1):
            blockIndex += 1
            block = childBlocks[blockIndex]
            blockType = block['type']
            if (blockType=='text'):
                txt += block['text']
            elif (blockType=='code'):
                codeResult = self.evaluateCodeBlock(block, lead)
                if ('text' in codeResult):
                    txt += codeResult['text']
                if ('action' in codeResult):
                    action = codeResult['action']
                    if (action == 'jumplead'):
                        # we want to create a new lead with contents of this one until next section
                        # create new lead
                        if (lead['properties']['label'] != ''):
                            label = lead['properties']['label'] + ' contd.'
                        else:
                            label = ''
                        newLead = self.migrateChildBlocksToNewLead(headBlock, label, block, blockIndex)
                        # resume from this blockindex afterwards
                        txt += self.makeTextLinkToLead(newLead)
            else:
                self.raiseBlockException(self, block, 0, 'Unknown block type "{}"'.format(blockType))

        # trim
        txt = txt.strip()

        return txt
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def migrateChildBlocksToNewLead(self, headBlock, label, block, blockIndex):
        # create new lead
        properties = {}

        # dynamically generated lead id
        leadId = self.consumeUnusedLeadId()
        # create a new head block with stats from this block
        if (label!=''):
            headerString ='{}: {}'.format(leadId, label)
        else:
            headerString = leadId
        newHeadBlock = self.makeBlockHeader(headerString, block['sourceLabel'], block['lineNumber'], 'lead')
        self.addHeadBlock(newHeadBlock)

        properties = newHeadBlock['properties']
        properties['id'] = leadId
        properties['renderId'] = leadId
        properties['sectionName'] = self.makeSectionNameForHeadBlock(newHeadBlock, leadId)

        # ok ADD the new lead by copying values from block
        lead = {'block': newHeadBlock, 'properties': properties, 'text': '', 'sourceLabel': newHeadBlock['sourceLabel'], 'lineNumber': newHeadBlock['lineNumber']}
        self.storeLeadId(leadId, lead)

        # now migrate children
        childBlocks = headBlock['blocks']
        while (blockIndex<len(childBlocks)-1):
            blockIndex += 1
            block = childBlocks[blockIndex]
            if (block['type']=='code'):
                properties = block['properties']
                if ('embeddedShortCode' not in properties) or (properties['embeddedShortCode']==False):
                    # we encountered a full code block so we are done
                    break
            # move this bock
            self.addChildBlock(newHeadBlock, block)
            del headBlock['blocks'][blockIndex]
            blockIndex -= 1

        # now process it (it will not be processed in main loop since it is added after)
        self.processLead(lead)

        return lead
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
    def isRenderTextSyntaxMarkdown(self):
        renderOptions = self.getOptionValThrowException('renderOptions')
        renderTextSyntax = renderOptions['textSyntax']
        if (renderTextSyntax=='markdown'):
            return True
        return False
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def makeTextLinkToLead(self, lead):
        properties = lead['properties']
        leadId = properties['id']
        renderId = properties['renderId']
        return self.makeTextLinkToLeadId(leadId, renderId)


    def makeTextLinkToLeadId(self, leadId, renderId):
        if (renderId[0].isdigit()):
            prefix='#'
        else:
            prefix = ''
        #
        if (self.isRenderTextSyntaxMarkdown()):
            text = '{}[{}](#{})'.format(prefix, renderId, renderId)
        else:
            text = prefix + renderId
        #
        return text
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def evaluateCodeBlock(self, block, lead):
        codeResult = {'text': ''}
        codeText = block['text']

        # parse code
        [funcName, args, pos] = self.parseFunctionCallAndArgs(block, codeText)

        if (funcName=='options'):
            # merge in options
            jsonOptionString = args['json']
            jsonOptions = json.loads(jsonOptionString)
            # set the WORKINGDIR options
            self.jroptionsWorkingDir.mergeRawDataForKey('options', jsonOptions)

        elif (funcName=='lead'):
            # replace with a lead's rendered id
            leadId = args['leadId']
            #
            lead = self.findLeadById(leadId)
            if (lead is None):
                self.raiseBlockException(self, block, 0, 'Unknown lead reference: "{}"'.format(leadId))
            #
            codeResult['text'] = self.makeTextLinkToLead(lead)

        elif (funcName=='tag'):
            # just replace with text referring to a tag
            # map it
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName)

            # track use
            tagDict['useCount'] += 1
            useNote = 'Referred to by lead "{}" from {} near line {}.'.format(lead['properties']['id'], block['sourceLabel'], block['lineNumber'])
            tagDict['useNotes'].append(useNote)

            # use it
            tagLabel = tagDict['label']
            codeResult['text'] = '{}'.format(tagLabel)

        elif (funcName=='gaintag'):
            # show someone text that they get a tag
            optionUseTagLetters = self.getTagsAsLetters()
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName)

            # track use
            tagDict['useCount'] += 1
            useNote = 'Gained tag in lead "{}" from {} near line {}.'.format(lead['properties']['id'], block['sourceLabel'], block['lineNumber'])
            tagDict['useNotes'].append(useNote)

            # use it
            tagLabel = tagDict['label']
            if (optionUseTagLetters):
                text = 'You have gained the requirement letter "{}"; please circle this letter in your records for later use (if you have not done so already).'.format(tagLabel)
            else:
                text = 'You have gained the requirement keyword "{}"; please note this keyword in your records for later use (if you have not done so already).'.format(tagLabel)
            #
            codeResult['text'] = text


        elif (funcName=='havetag'):
            # show someone text that checking a tag
            optionUseTagLetters = self.getTagsAsLetters()
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName)

            # track use
            tagDict['useCount'] += 1
            useNote = 'Checking if users has tag in lead "{}" from {} near line {}.'.format(lead['properties']['id'], block['sourceLabel'], block['lineNumber'])
            tagDict['useNotes'].append(useNote)

            # use it
            tagLabel = tagDict['label']
            if (optionUseTagLetters):
                text = 'If you have gained (circled) the requirement letter "{}"'.format(tagLabel)
            else:
                text = 'If you have gained the requirement keyword "{}"'.format(tagLabel)
            codeResult['text'] = text


        elif (funcName=='missingtag'):
            # show someone text that checking a tag
            optionUseTagLetters = self.getTagsAsLetters()
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName)

            # track use
            tagDict['useCount'] += 1
            useNote = 'Checking if users DOES NOT HAVE tag in lead "{}" from {} near line {}.'.format(lead['properties']['id'], block['sourceLabel'], block['lineNumber'])
            tagDict['useNotes'].append(useNote)

            # use it
            tagLabel = tagDict['label']
            if (optionUseTagLetters):
                text = 'If you have *NOT* gained (circled) the requirement letter "*{}*"'.format(tagLabel)
            else:
                text = 'If you have *NOT* gained the requirement keyword "*{}*"'.format(tagLabel)
            codeResult['text'] = text

        elif (funcName=='jumplead'):
            # tricky one, this moves the subsqeuent text blocks into a new dynamically assigned lead and returns the lead #
            codeResult['text'] = ''
            codeResult['action'] = 'jumplead'

        elif (funcName=='endjump'):
            # tricky one, this moves the subsqeuent text blocks into a new dynamically assigned lead and returns the lead #
            codeResult['text'] = ''

        elif (funcName=='insertlead'):
            # insert contents of a lead here
            leadId = args['leadId']
            lead = self.findLeadById(leadId)
            if (lead is None):
                self.raiseBlockException(self, block, 0, 'Unknown lead reference: "{}"'.format(leadId))
            text = self.evaluateHeadBlockTextCode(lead)
            codeResult['text'] = text
        else:
            if (True):
                # debug
                dbgObj = {'funcName': funcName, 'args': args, 'pos': pos}
                text = json.dumps(dbgObj)
                codeResult = {'text': text}
                jrprint('WARNING: code function not understood: {}'.format(text))
            else:
                # debug
                codeResult = {'text': '{' + codeText + '}'}

        return codeResult
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def getTagsAsLetters(self):
        return self.getOptionVal('tagsAsLetters', False)


    def findOrMakeTagDictForTag(self, tagName):
        tagName = tagName.upper()
        if (tagName in self.tagMap):
            tagDict = self.tagMap[tagName]
        else:
            label = self.makeTagLabel(tagName)
            tagDict = {'label': label, 'useCount': 0, 'useNotes': []}
            self.tagMap[tagName] = tagDict
        return tagDict


    def makeTagLabel(self, tagName):
        #
        optionUseTagLetters = self.getTagsAsLetters()

        # initialize list if empty
        if (len(self.tagLabelsAvailable)==0):
            # refresh it
            self.tagLabelStage += 1
            if (self.tagLabelStage == 1):
                suffix = ''
            else:
                suffix = str(self.tagLabelStage)
            self.tagLabelsAvailable = list = [chr(item)+suffix for item in range(ord("A"), ord("Z") + 1)]
            random.shuffle(self.tagLabelsAvailable)

        # use random letters as tags
        if (optionUseTagLetters):
            # try to use first letter of tag
            firstLetter = tagName[0].upper()
            if (firstLetter in self.tagLabelsAvailable):
                self.tagLabelsAvailable.remove(firstLetter)
                label = firstLetter
            else:
                label = self.tagLabelsAvailable.pop()
        else:
            label = tagName
        #
        return label
# ---------------------------------------------------------------------------














































































# ---------------------------------------------------------------------------
    def renderLeads(self):
        jrprint('Rendering leads..')

        # options
        renderOptions = self.getOptionValThrowException('renderOptions')
        renderFormat = renderOptions['format']
        #
        info = self.getOptionValThrowException('info')
        chapterName = info['chapterName']
        chapterTitle = info['chapterTitle']
        chapterAuthor = info['author']
        chapterVersion = info['version']
        chapterDate = info['date']
        buildDate = jrfuncs.getNiceCurrentDateTime()

        if (renderFormat!='html'):
            raise Exception('Only html lead rendering currently supported, not "{}".'.format(renderFormat))

        # where to save
        defaultSaveDir = self.getOptionValThrowException('savedir')
        saveDir = self.getOptionVal('chapterSaveDir', defaultSaveDir)
        outFilePath = '{}/{}.html'.format(saveDir,chapterName)
        outFilePath = self.resolveTemplateVars(outFilePath)

        # sort leads into sections
        self.sortLeadsIntoSections()

        #
        jrprint('Rendering leads to: {}'.format(outFilePath))
        encoding = self.getOptionValThrowException('storyFileEncoding')
        with open(outFilePath, 'w', encoding=encoding) as outfile:
            # html start
            html = '<html>\n'
            html += '<head><meta http-equiv="Content-type" content="text/html">\n'
            html += '<link rel="stylesheet" type="text/css" href="hl.css">'
            html += '<title>{}</title>\n'.format(chapterTitle)
            html += '</head>\n'
            html += '<body>\n'
            outfile.write(html)

            # front page
            html = ''
            html += '<div class="chapterTitle">{}</div>\n'.format(chapterTitle)
            html += '<div class="chapterAuthor">{}</div>\n'.format(chapterAuthor)
            html += '<div class="chapterVersion">{}</div>\n'.format(chapterVersion)
            html += '<div class="chapterDate">{}</div>\n'.format(chapterDate)
            html += '<div class="buildDate">(built {})</div>\n'.format(buildDate)
            html += '<div class="pagebreakafter"></div>\n'
            html += '\n\n\n\n'
            outfile.write(html)

            # leads start
            html = '<article class="leads">\n'
            outfile.write(html)

            # iterate sections
            self.renderSection(self.rootSection, outfile, renderFormat)

            # leads end
            html += '</article>\n'
            outfile.write(html)

            # doc end
            html = '</body>\n'
            outfile.write(html)



    def renderSection(self, section, outfile, renderFormat):
        # leads
        if ('leads' in section):
            leads = section['leads']
            if (len(leads)>0):
                self.renderSectionLeads(leads, section, outfile, renderFormat)
        else:
            # blank leads just show section page
            if ('label' in section):
                self.renderSectionLeads({}, section, outfile, renderFormat)

        # recurse children
        if ('sections' in section):
            childSections = section['sections']
            for childid, child in childSections.items():
                self.renderSection(child, outfile, renderFormat)


    def renderSectionLeads(self, leads, section, outfile, renderFormat):
        renderOptions = self.getOptionValThrowException('renderOptions')
        renderSectionHeaders = renderOptions['sectionHeaders']
        renderLeadLabels = renderOptions['leadLabels']
        renderTextSyntax = renderOptions['textSyntax']
        #
        showedHead = False
        #
        html = ''

        # section header
        sectionLabel = section['label']

        # iterate leads
        for leadid, lead in leads.items():
            leadProperties = lead['properties']
            id = leadProperties['renderId']
            #
            flagRender = leadProperties['render'] if ('render' in leadProperties) else True
            if (flagRender=='false'):
                continue

            if (not showedHead):
                showedHead = True
                html += '<div class="leadsection">\n'
                # section breaks
                if (renderSectionHeaders):
                    html += '\n\n<h1>{}</h1>\n\n'.format(sectionLabel)

            # lead start
            html += '<div class="lead">\n'

            # lead label
            html += '<h2 id="{}">{}</h2>\n'.format(id, id)
            
            leadLabel = leadProperties['label'] if ('label' in leadProperties) else ''
            if (renderLeadLabels) and (leadLabel!=''):
                html += '<h3>{}</h3>\n'.format(leadLabel)

            # lead text
            txtRenderedToHtml = self.renderTextSyntax(renderTextSyntax, lead['text'])
            html += '<div class="leadtext">{}</div>\n\n'.format(txtRenderedToHtml)

            # lead end
            html += '</div> <!-- lead -->\n'

        # end of leads in this section
        if (showedHead):
            html += '</div> <!-- lead section -->\n\n'

        # write it
        outfile.write(html)
# ---------------------------------------------------------------------------


















# ---------------------------------------------------------------------------
    def renderTextSyntax(self, renderTextSyntax, text):
        if (renderTextSyntax=='html'):
            # html is as is
            return text
        if (renderTextSyntax=='plainText'):
            # plaintext needs newlines into <p>s
            text = text.strip()
            textLines = text.split('\n')
            html = ''
            for line in textLines:
                html += '<p>{}</p>\n'.format(line)
            return html
        if (renderTextSyntax=='markdown'):
            # markdown
            # using mistletoe library
            html = self.renderMarkdown(text)
            return html
        #
        raise Exception('renderTextSyntax format not understood: {}.'.format(renderTextSyntax))
    


    def renderMarkdown(self, text):
        return self.hlMarkdown.renderMarkdown(text)
# ---------------------------------------------------------------------------





















