# helper class for hl parser tool

from lib.jr import jrfuncs
from lib.jr import jroptions
from lib.jr.jrfuncs import jrprint
from lib.jr.jrfuncs import jrException

from lib.jr.hlmarkdown import HlMarkdown
import hlapi
from lib.jr import jrmindmap

# python modules
import re
import os
import pathlib
from collections import OrderedDict
import json
import random
import argparse


# ---------------------------------------------------------------------------
buildVersion = '2.0jr'
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
class HlParser:

    def __init__(self, optionsDirPath, overrideOptions={}):
        # load options
        self.jroptions = None
        self.jroptionsWorkingDir = None
        self.storyFileList = []
        self.headBlocks = []
        self.leads = []

        self.warnings = []
        self.dynamicLeadMap = {}
        self.leadSections = {}
        self.tagMap = {}
        self.tagLabelsAvailable = [] #list(map(chr, range(ord('A'), ord('Z')+1)))
        self.tagLabelStage = 0
        self.notes = []
        random.shuffle(self.tagLabelsAvailable)
        #
        self.userVars = {}
        self.tText = {'goto': 'go to'}
        #
        self.markBoxesTracker = {}
        #
        self.argDefs = {
            'header': {
                'named': ['id', 'label', 'existing', 'ignore', 'section', 'type', 'warning', 'autoid', 'render', 'sort'],
                'positional': ['id', 'label'],
                'required': []
            },
            'tag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'golead': {'named': ['leadId'], 'positional': ['leadId'], 'required': ['leadId']},
            'options': {'named': ['json'], 'positional': ['json'], 'required': ['json']},
            'inline': {'named': ['id', 'label'], 'positional': ['id', 'label']},
            'gaintag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'havetag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'haveanytag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'havealltags': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'missingtag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'requiretag': {'named': ['tagName'], 'positional': ['tagName'], 'required': ['tagName']},
            'beforeday': {'named': ['day'], 'positional': ['day'], 'required': ['day']},
            'afterday': {'named': ['day'], 'positional': ['day'], 'required': ['day']},
            'onday': {'named': ['day'], 'positional': ['day'], 'required': ['day']},
            'ifcond': {'named': ['cond'], 'positional': ['cond'], 'required': ['cond']},
            'endjump': {},
            'insertlead': {'named': ['leadId'], 'positional': ['leadId'], 'required': ['leadId']},
            'get': {'named': ['varName'], 'positional': ['varName'], 'required': ['varName']},
            'set': {'named': ['varName', 'value'], 'positional': ['varName', 'value'], 'required': ['varName', 'value']},
            'empty': {},
            'markovertime': {'named': ['amount'], 'positional': ['amount']},
            'markdemerit': {'named': ['amount'], 'positional': ['amount']},
            'markculture': {'named': ['amount'], 'positional': ['amount']},
            'headback': {'named': ['demerits', 'goto'], 'positional': ['demerits']},
            'retrieve': {'named': ['label', 'comment'], 'positional': ['label', 'comment'], 'required': ['label']},
            'form': {'named': ['type','choices'], 'positional': ['type', 'choices'], 'required': ['type']},
            'report': {'named': ['comment'], 'positional': ['comment']},
            'otherwise': {},
        }
        #
        self.doLoadAllOptions(optionsDirPath, overrideOptions)
        #
        renderOptions = self.getOptionValThrowException('renderOptions')
        markdownOptions = renderOptions['markdown']
        self.hlMarkdown = HlMarkdown(markdownOptions)
        #
        # hl api
        hlApiOptions = self.getOptionVal('hlApiOptions', {})
        baseDir = self.getOptionValThrowException('basedir')
        hlDataDir = self.getOptionVal('hlDataDir', baseDir + '/options/hldata')
        hlDataDir = self.resolveTemplateVars(hlDataDir)
        self.hlapi = hlapi.HlApi(hlDataDir, hlApiOptions)
        #
        # mindmap
        mindMapOptions = self.getOptionVal('mindMapOptions', {})
        self.mindMap = jrmindmap.JrMindMap(mindMapOptions)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
    def getVersion(self):
        return buildVersion
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def runAll(self):
        self.loadStoryFilesIntoBlocks()
        #
        self.processHeadBlocks()
        self.processLeads()
        self.postProcesMindMap()
        self.saveLeads()
        self.renderLeadsDual()
        #
        self.saveAllManualLeads()
        #
        self.saveAltStoryFilesAddLeads()
        #
        self.saveMindMapStuff()
        #
        self.debug()
        self.reportNotes()
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
    def calcOutFileDerivedName(self, baseFileName):
        saveDir = self.getOptionValThrowException('savedir')
        saveDir = self.resolveTemplateVars(saveDir)
        jrfuncs.createDirIfMissing(saveDir)
        info = self.getOptionValThrowException('info')
        chapterName = jrfuncs.getDictValueOrDefault(info, 'chapterName', '')
        outFilePath = saveDir + '/' + chapterName + baseFileName
        return outFilePath
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


    def saveAltStoryFilesAddLeads(self):
        for filePath in self.storyFileList:
            self.saveAltStoryFile(filePath)
    

    def saveAltStoryFile(self, filePath):
        outFilePath = filePath.replace('.txt','.labeled')
        if (outFilePath == filePath):
            outFilePath = filePath + '.labeled'
        jrprint('Saving version of storyfile with labels added: {}'.format(outFilePath))
        # load it
        encoding = self.getOptionValThrowException('storyFileEncoding')
        fileText = jrfuncs.loadTxtFromFile(filePath, True, encoding)
        # 
        leadHeadRegex = re.compile(r'^# ([^:\(\)\/]*[^\s])(\s*\(.*\))?(\s*\/\/.*)?$')
        # walk it and write it
        with open(outFilePath, 'w', encoding=encoding) as outfile:
            lines = fileText.split('\n')
            for line in lines:
                matches = leadHeadRegex.match(line)
                if (matches is not None):
                    # got a match - can we find an id?
                    leadId = matches[1].strip()
                    [existingLeadRow, existingRowSourceKey] = self.hlapi.findLeadRowByLeadId(leadId)
                    if (not existingLeadRow is None):
                        # found a lead
                        label = self.calcLeadLabelForLeadRow(existingLeadRow)
                        if (':' in label) or ('(' in label) or (')' in label):
                            label = '"{}"'.format(label)
                        line = '# {}: {}'.format(leadId, label)
                        if (matches.group(2) is not None):
                            line += matches.group(2)
                        if (matches.group(3) is not None):
                            line += matches.group(3)

                #
                outfile.write(line+'\n')
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
        lineNumberStart = 0
        posOnLine = -1
        cprev = ''
        #
        text = self.earlyTextReplacements(text, sourceLabel)
        #
        validShortCodeStartCharacterList = 'abcdefghijklmnopqrstuvwxyz'
        #
        trackEnclosusers = {'comment': [], 'code': []}
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
                # FIRST we need to kick out of single line comment (very imp)
                if (inSingleLineComment):
                    # single line comments end at end of line
                    inSingleLineComment = False
                    # now we drop down to handle end of single line head

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





            # warnings
            if (c=='#') and (cnext==' ') and (posOnLine==1) and ((inCodeBlackDepth>0) ):
                jrprint('WARNING: got a header inside a code block; source: {} line: {} pos: {}'.format(sourceLabel, lineNumber, posOnLine))
            if (c=='#') and (cnext==' ') and (posOnLine==1) and ((inBlockCommentDepth>0) ):
                jrprint('WARNING: got a header inside a comment block; source: {} line: {} pos: {}'.format(sourceLabel, lineNumber, posOnLine))

            if (inSingleLineComment):
                # we are on a comment line, just ignore it
                continue
            #
            if (c=='/') and (cnext=='*'):
                # blockComment start
                i+=1
                inBlockCommentDepth += 1
                if (inBlockCommentDepth==1):
                    # clear current text block
                    curTextBlock = None
                trackEnclosusers['comment'].append('line {} pos {}'.format(lineNumber,posOnLine))
                continue
            if (c=='*') and (cnext=='/'):
                # blockComment end
                i+=1
                inBlockCommentDepth -= 1
                trackEnclosusers['comment'].pop()
                if (inBlockCommentDepth<0):
                    self.raiseParseException('End of comment block "*/" found without matching start.', i, posOnLine, lineNumber, text, sourceLabel)
                continue
            if (inBlockCommentDepth>0):
                # in multi-line comment, ignore it
                continue
            #
            if (c=='/') and (cnext=='/'):
                # single comment line start
                inSingleLineComment = True
                continue

            #
            if (c=='{') and (not inSingleLineHead):
                # code block start
                inCodeBlackDepth += 1
                trackEnclosusers['code'].append('line {} pos {}'.format(lineNumber,posOnLine))
                if (inCodeBlackDepth==1):
                    # outer code block { does not capture
                    # clear current text block
                    curTextBlock = None
                    codeBlockStartLineNumber = lineNumber
                    lastStartLabelCodeBlock = 'line {} pos {}'.format(lineNumber,posOnLine)
                    continue
            if (c=='}') and (not inSingleLineHead):
                # code block end
                inCodeBlackDepth -= 1
                trackEnclosusers['code'].pop()
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
            stackHistoryString = ';'.join(trackEnclosusers['code'])
            self.raiseParseException('Unexpected end of text while inside code block [stack {}].'.format(stackHistoryString), i, posOnLine, lineNumber, text, sourceLabel)
        if (inBlockCommentDepth>0):
            stackHistoryString = ';'.join(trackEnclosusers['comment'])
            self.raiseParseException('Unexpected end of text while inside comment block  [stack {}].'.format(stackHistoryString), i, posOnLine, lineNumber, text, sourceLabel)

        # and eof which can help stop us from following one lead to subsequent one from another file
        block = self.makeBlockEndFile(sourceLabel, lineNumber)
        self.addChildBlock(headBlock, block)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    def raiseParseException(self, msg, posInText, posOnLine, lineNumber, text, sourceLabel):
        msgExpanded = 'Parsing error: {} in {} at line {} pos {}.'.format(msg, sourceLabel, lineNumber, posOnLine)
        jrprint(msgExpanded)
        raise Exception(msgExpanded)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
    def earlyTextReplacements(self, text, sourceLabel):
        # do some early text replacements
        intext = text
        regexSpaceBullets = re.compile(r'^ \. ', re.MULTILINE)
        text = regexSpaceBullets.sub(' * ', text)
        return text
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
            label = None
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
        self.handleSpecialHeadIdProperties(id, properties)


        # store properties
        block['properties'] = properties

        return block
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def handleSpecialHeadIdProperties(self, id, properties):
        # kludge to handle specially named head leads/sections
        if (id=='options'):
            properties['type']= 'options'
            properties['raw'] = True
        if (id=='comments'):
            properties['type']= 'comments'
            properties['raw'] = True
        if (id=='cover'):
            properties['noid']= True
            properties['section'] = 'cover'
            optionCssdocstyle = self.getOptionValThrowException('cssdocstyle')
            properties['pageBreakAfter'] = True
        if (id=='debugReport'):
            properties['noid']= True
            properties['section'] = 'debugReport'
            optionCssdocstyle = self.getOptionValThrowException('cssdocstyle')
            properties['pageBreakAfter'] = True
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
        wrapperCharList = ['"', "'", '{', '“', '”']
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
            elif (c=='“'):
                openingChar = '“'
                closingChar = '”'
                keepFinalClose = False
                extractedText = ''
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

        if (text.strip()==''):
            # just an empty placeholder
            return ['empty', {}, 0]

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
    def processHeadBlocks(self):
        # first we make a pass for EARLY stage processing
        # we need to do this in multiple stages because we do NOT want to fully process a lead if it is overwritten by another later
        jrprint('Parsing {} head blocks..'.format(len(self.headBlocks)))
        for block in self.headBlocks:
            self.processHeadBlock(block)


    def processLeads(self):
        # now process leads
        jrprint('Processing {} leads..'.format(len(self.leads)))
        # note we have to get keys as list here and then iterate because self.leads changes
        leadCount = len(self.leads)
        for i in range(0,leadCount):
            lead = self.leads[i]
            self.processLead(lead)
        
        # we now do a second stage walking through leads fixing up BLANK ones that should copy the ones below them
        leadCount = len(self.leads)
        blockTextLen = 0
        for i in range(0, leadCount):
            lead = self.leads[i]
            self.fixupEmptyCopyLeads(lead, i)
            blockTextLen += len(lead['text'])

        jrprint('FINISHED PROCESSING {} LEADS ({:.2f}k of text).'.format(len(self.leads), blockTextLen / 1000))



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
            existingLead = self.findLeadById(id, True)
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

            # render id
            autoid = jrfuncs.getDictValueFromTrueFalse(properties, 'autoid', False)
            if (autoid):
                # assign a free leads id
                renderId = self.assignDynamicLeadId(id, block)
                properties['renderId'] = renderId
                properties['autoid'] = autoid
            else:
                renderId = id
            properties['renderId'] = renderId

            # store section name in properties
            properties['sectionName'] = self.makeSectionNameForHeadBlock(block, renderId)

            # for mindmaps
            properties['mtype'] = 'normal'

            # ok ADD the new lead by copying values from block
            lead = {'id': self.canonicalLeadId(id), 'block': block, 'properties': properties, 'text': blockText, 'sourceLabel': block['sourceLabel'], 'lineNumber': block['lineNumber']}
            self.addLead(lead)

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
    def fixupEmptyCopyLeads(self, lead, leadIndex):
        # this is used to let us specify a long list of lead # headers with text only in the last one
        if (lead['text']!=''):
            # non-empty, nothing to do
            return
        headBlock = lead['block']
        if ('blocks' in headBlock):
            childBlocks = headBlock['blocks']
            if (len(childBlocks)>0):
                # it has children of some sort so nothing to do even if it has no text
                return
        # no children
        # ok now walk forward and find first non-blank one to copy from
        leadCount = len(self.leads)
        for i in range(leadIndex+1, leadCount):
            nextLead = self.leads[i]
            if (nextLead['text']!=''):
                # copy from this one
                lead['text'] = nextLead['text']
                lead['reportText'] = nextLead['reportText']
                jrprint('Copying text from lead {} into blank lead {}.'.format(nextLead['id'], lead['id']))
                return
        # couldnt find one to copy from
        return
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
    def processLead(self, lead):
        manualLeadIgnoreList = ['0-0000']
        leadProprties = lead['properties']
        headBlock = lead['block']
        #
        leadId = lead['id']
        label = leadProprties['label'] if ('label' in leadProprties) else None
        autoid = leadProprties['autoid'] if ('autoid' in leadProprties) else False
        #
        [existingLeadRow, existingRowSourceKey] = self.hlapi.findLeadRowByLeadId(leadId)
        if (existingLeadRow is not None):
            existingLeadRowLabel = existingLeadRow['properties']['dName']
            existingLeadRowAddress = existingLeadRow['properties']['address']
        else:
            existingLeadRowLabel = ''
            existingLeadRowAddress = ''

        # warnings
        warningVal = jrfuncs.getDictValueOrDefault(leadProprties, 'warning', None)
        if (warningVal is not None):
            msg = 'Manual warning set: {}'.format(warningVal)
            self.appendWarningLead(msg, lead)

        # if label not specified try to infer it
        if (label is None):
            # try to take it from existing row or make it blank
            if (existingLeadRowLabel!=''):
                label = self.calcLeadLabelForLeadRow(existingLeadRow)
                leadProprties['label'] = label
            else:
                label = ''
        if (label == '.') or (label=="blank"):
            # shorthand for make blank
            label = ''

        # smart label compare
        needsCompare = False
        prefix = ' '
        if (autoid):
            # this should NOT match
            if (existingLeadRow is not None):
                msg = 'An autoid lead should not match an existing lead in the database, but it does: {} at {} from {}'.format(existingLeadRow['dName'], existingLeadRow['address'], existingRowSourceKey)
                self.appendWarningLead(msg, lead)
                needsCompare = True
        else:
            # not an autoid so we expect to match it
            if (leadId[0].isalpha()) or (leadId in manualLeadIgnoreList):
                # it doesnt start with a number so we dont expect it to match
                if (existingLeadRow is not None):
                    msg = 'WARNING: A lead starting with a letter should not match an existing lead in the database, but it does: {} at {} from {}.'.format(existingLeadRow['dName'], existingLeadRow['address'], existingRowSourceKey)
                    self.appendWarningLead(msg, lead)
                    needsCompare = True
            else:
                # a number lead should match
                if (existingLeadRow is None):
                    needsCompare = True

        if (needsCompare) or (existingLeadRow is not None):
            if (existingLeadRow is None):
                if (label==''):
                    labelCompareStr = ''
                else:
                    labelCompareStr = '[{}]'.format(label)
                if (needsCompare):
                    searchFor = label if (label!='') else leadId
                    [guessLead, guessSource] = self.hlapi.findLeadRowByNameOrAddress(searchFor)
                    if (guessLead is None):
                        # let's try a SLOWER metric search
                        [guessLead, guessSource, dist] = self.hlapi.findLeadRowSimilarByNameOrAddress(searchFor)
                    else:
                        dist = 0
                    #
                    if (guessLead is None):
                        msg = 'WARNING: A numbered lead is expected to match an existing lead in the database, but it does not; from {} at line #{}.'.format(lead['sourceLabel'], lead['lineNumber']+1)
                        labelCompareStr += ' vs [NOT FOUND IN DB]'
                    else:
                        msg = 'WARNING: A numbered lead is expected to match an existing lead in the database, but it does not; MAYBE: #{} - "{}" from {}? (dist {:.2f})].'.format(guessLead['properties']['lead'], guessLead['properties']['dName'], guessSource, dist)
                        labelCompareStr += ' vs [NOT FOUND MAYBE: #{} - "{}" from {}? (dist {:.2f})]'.format(guessLead['properties']['lead'], guessLead['properties']['dName'], guessSource, dist)
                    self.appendWarningLead(msg, lead)
                    #                     
                    prefix = '*'
            elif (label == existingLeadRowLabel):
                labelCompareStr = '[{} vs SAME @ {}]'.format(label, existingLeadRowAddress)
            else:
                labelCompareStr = '[{}] vs [{} @ {}]'.format(label, existingLeadRowLabel, existingLeadRowAddress)
        else:
            labelCompareStr = '[{}]'.format(label)
        
        if (labelCompareStr != '') and (autoid):
            prefix = 'A'
        
        if (prefix==' ') and (leadId[0].isdigit()) and (label == ''):
            # blank label on a numerical lead id is a warning
            prefix = '-'
        
        # add prefix to help identify the nature of the lookup on the lead
        labelCompareStr = prefix + labelCompareStr

        debugInfo = '{} ..... from {} at line #{}'.format(labelCompareStr, lead['sourceLabel'], lead['lineNumber']+1)
        jrprint('Processing lead {:.<20}... {}'.format(leadId, debugInfo))
        #
        # normal full text contents of the lead; note the second time lead is passed it is the behalfLead; for normal building of text this is the case; if the lead is built to embed elsewhere this will be different
        [normalText, reportText] = self.evaluateHeadBlockTextCode(lead, lead, {})
        lead['text'] = normalText
        lead['reportText'] = reportText
        lead['debugInfo'] = debugInfo
        # lets store the existing lead row in hl data
        lead['existingLeadRow'] = existingLeadRow
# ---------------------------------------------------------------------------

























# ---------------------------------------------------------------------------
    def findLeadById(self, leadId, flagCheckRenderId):
        leadId = self.canonicalLeadId(leadId)

        if (leadId=='1235'):
            jrprint('DEBUG')

        for lead in self.leads:
            propLeadId = lead['id']
            if (propLeadId == leadId):
                return lead
            if (flagCheckRenderId):
                if (lead['properties']['renderId']==leadId):
                    return lead

        return None

    def addLead(self, lead):
        #jrprint('Storing lead: {}.'.format(leadId))
        leadIndex = len(self.leads)
        lead['leadIndex'] = leadIndex
        self.leads.append(lead)
        # add mind map
        self.mindMapLead(lead)

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
        saveDir = self.resolveTemplateVars(saveDir)
        jrfuncs.createDirIfMissing(saveDir)
        outFilePath = saveDir + '/leadsout.json'
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
        self.rootSection['sections'] = jrfuncs.deepCopyListDict(optionSections)
        #self.createRootChildSection('Front', 'Front', '010')
        #self.createRootChildSection('Leads', 'Leads', '020')
        #self.createRootChildSection('Back', 'Back', '030')

        self.addMissingSections()

        #
        for lead in self.leads:
            leadId = lead['id']
            section = self.calcSectionForLead(lead)
            if ('leads' not in section):
                section['leads'] = {}
            section['leads'][leadId] = lead
        
        # now walk sections and sort leads and subsections
        if (len(self.rootSection)>0):
            self.sortSection(self.rootSection, 'index')


    def getDefaultSections(self):
        defaultSections = {
		"Briefings": {"label": "Briefings", "sort": "010", "leadsort": "index", "cssStyle": "onecolumn"},
		"Main": {"label": "Main Leads", "sort": "050", "leadsort": "alpha"},
		"End": {"label": "End", "sort": "100", "leadsort": "index", "cssStyle": "onecolumn"},
	    }
        return defaultSections
    

    def addMissingSections(self):
        if ('cover' not in self.rootSection['sections']):
            self.createRootChildSection('cover','', '002a', 'index', 'onecolumn')
        if ('debugReport' not in self.rootSection['sections']):
            self.createRootChildSection('debugReport','Debug Report', '002b', 'index', 'onecolumn')


    def createRootChildSection(self, id, label, sortOrder, leadSort, cssStyle):
        parentSection = self.rootSection
        if ('sections' not in parentSection):
            # no children, add it
            parentSection['sections'] = {}
        if (id not in parentSection['sections']):
            parentSection['sections'][id] = {'id': id, 'label': label, 'sort': sortOrder, 'leadSort': leadSort, 'cssStyle': cssStyle}


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
        jrprint('\nTag map:')
        jrprint(self.tagMap)
        if (False):
            jrprint('Headblocks:\n')
            for block in self.headBlocks:
                blockDebugText = self.calcDebugBlockText(block)
                jrprint(blockDebugText)
        jrprint('---------------------------\n')
        self.mindMap.debug()


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
            jrprint('[{}]: {}'.format(index+1, warning['text']))
        jrprint('\n')

    def reportNotes(self):
        if (len(self.notes)==0):
            jrprint('{} notes.'.format(len(self.warnings)))
            return
        jrprint('{} notes:'.format(len(self.notes)))
        for index, note in enumerate(self.notes):
            jrprint('[{}]: {}'.format(index+1, note['text']))
        jrprint('\n')
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
        if (not 'text' in block):
            lineNumber = 0
            linePos = 0
        else:
            [lineNumber, linePos] = self.countLinesInBlockUntilPos(block['text'], pos)
        #

        msg = message + ' (at pos {}).'.format(linePos)
        self.raiseBlockException(block, lineNumber, msg)


    def countLinesInBlockUntilPos(self, text, pos):
        lineNumber = 0
        linePos = 0
        for i in range(0,pos):
            c = text[i]
            if (c=='\n'):
                linePos = 0
                lineNumber += 1
        return [lineNumber, linePos]
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
        oldLead = self.findLeadById(renderId, True)
        if (oldLead is not None):
            self.raiseBlockException(block, 0, 'ERROR: unused lead returned an id ({}) that already exists in lead table ({} at {}) for DYNAMIC lead id "{}"'.format(renderId, oldLead['sourceLabel'], oldLead['lineNumber'], id))
        self.dynamicLeadMap[id] = renderId
        return renderId
    
    def consumeUnusedLeadId(self):
        unusedLeadRow = self.hlapi.popAvailableLead()
        if (unusedLeadRow is None):
            # not found, unavailable from list.
            # so instead make a random one
            while (True):
                randomid = 'R-{}{}{}{}'.format(random.randint(0, 9), random.randint(0, 9), random.randint(0, 9), random.randint(0, 9))
                oldLead = self.findLeadById(randomid, True)
                if (oldLead is None):
                    break
            return randomid

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
                self.raiseBlockException(block, 0, 'Unknown block type "{}"'.format(blockType))

        # trim
        txt = txt.strip()

        return txt
# ---------------------------------------------------------------------------
    






# ---------------------------------------------------------------------------
# ok here is our new code to evaluate blocks
    def evaluateHeadBlockTextCode(self, lead, behalfLead, evaluationOptions):
        # this now returns the tupe [normalText, reportText]
        headBlock = lead['block']
        if ('blocks' not in headBlock):
            return ['', '']
        
        # assemble
        text = ''
        reportText = ''
        #
        childBlocks = headBlock['blocks']
        blockIndex = -1
        while (blockIndex<len(childBlocks)-1):
            blockIndex += 1
            block = childBlocks[blockIndex]
            blockType = block['type']
            if (blockType=='text'):
                text += block['text']
                reportText += block['text']
            elif (blockType=='code'):
                textPositionStyle = self.calcTextPositionStyle(text)
                codeResult = self.evaluateCodeBlock(block, lead, textPositionStyle, behalfLead, evaluationOptions)
                if ('text' in codeResult):
                    text += codeResult['text']
                if ('reportText' in codeResult):
                    reportText += codeResult['reportText']
                #
                if ('action' in codeResult):
                    action = codeResult['action']
                    if (action == 'inline'):
                        # we want to create a new lead with contents of this one until next section
                        # label?
                        if ('label' in codeResult['args']):
                            label = codeResult['args']['label']
                        else:
                            oLeadLabel = lead['properties']['label'] if (lead['properties']['label'] != '') and (lead['properties']['label'] is not None) else lead['id']
                            labelContd = ' ({}) contd.'.format(self.makeTextLinkToLead(lead, False))
                            label = oLeadLabel + labelContd
                        #
                        forcedLeadId = jrfuncs.getDictValueOrDefault(codeResult['args'], 'id', '')
                        [newLead, addTextSuffix] = self.inlineChildBlocksToNewLead(lead, headBlock, label, block, blockIndex, forcedLeadId)
                        # resume from this blockindex afterwards
                        linkText = self.makeTextLinkToLead(newLead, False)
                        baseText = self.getText('goto') + ' ' + linkText
                        textPositionStyle = self.calcTextPositionStyle(text)
                        baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
                        baseText += addTextSuffix
                        text += baseText
                        reportText += baseText
                        # mindmap
                        self.createMindMapLinkLeadGoesToLead(lead, newLead, True)
            elif (blockType=='eof'):
                # nothing to do
                pass
            else:
                self.raiseBlockException(block, 0, 'Unknown block type "{}"'.format(blockType))

        # trim
        text = text.strip()
        reportText = reportText.strip()

        return [text, reportText]
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def calcTextPositionStyle(self, text):
        # return one of: ['linestart', 'sentence', 'midsentence']
        # linestart: next text starts a line
        # sentence: next text starts a sentence (could be after a : for example
        # midstentence: should start with lowercase
        spaceCharacters = [' ']
        setenceCharacters = [':', '.', '@', '$', '&', '*']
        linestartCararacters = ['\n', '\t']
        #
        if (len(text)==0):
            return 'linestart'
        pos = len(text)-1
        while (pos>=0):
            c = text[pos]
            pos -= 1
            if (c in spaceCharacters):
                continue
            if (c in setenceCharacters):
                return 'sentence'
            if (c in linestartCararacters):
                return 'linestart'
            # something else
            return 'midsentence'
        # at start of line
        return 'linestart'


    def modifyTextToSuitTextPositionStyle(self, text, textPositionStyle, linestartPrefix):
        if (len(text)==0):
            return text
        #
        c = text[0]
        if (textPositionStyle in ['linestart', 'sentence']):
            if (c.isalpha):
                text= c.upper() + text[1:]
        elif (textPositionStyle in ['linestart', 'midsentence']):
            if (c.isalpha()):
                text = c.lower() + text[1:]
        #
        if (textPositionStyle=='linestart'):
            text = linestartPrefix + text
        return text
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def inlineChildBlocksToNewLead(self, sourceLead, headBlock, label, block, blockIndex, forcedLeadId):
        # create new lead
        properties = {}
        addTextSuffix = ''

        # dynamically generated lead id? or forced
        if (forcedLeadId==''):
            leadId = self.consumeUnusedLeadId()
            autoid = True
        else:
            leadId = forcedLeadId
            autoid = False
        #
        oldLead = self.findLeadById(leadId, True)
        if (oldLead is not None):
            self.raiseBlockException(block, 0, 'ERROR: inlining dynamic lead returned an id ({}) that already exists in lead table ({} at {}) for DYNAMIC lead id "{}"'.format(leadId, oldLead['sourceLabel'], oldLead['lineNumber'], id))

        # create a new head block with stats from this block
        if (label!=''):
            headerString ='{}: "{}"'.format(leadId, label)
        else:
            headerString = leadId
        newHeadBlock = self.makeBlockHeader(headerString, block['sourceLabel'], block['lineNumber'], 'lead')
        self.addHeadBlock(newHeadBlock)

        properties = newHeadBlock['properties']
        properties['renderId'] = leadId
        properties['sectionName'] = self.makeSectionNameForHeadBlock(newHeadBlock, leadId)
        properties['autoid'] = autoid

        # mtype is a trail from original lead plus inline
        properties['mtype'] = sourceLead['properties']['mtype'] + '.inline'

        # ok ADD the new lead by copying values from block
        lead = {'id': self.canonicalLeadId(leadId), 'block': newHeadBlock, 'properties': properties, 'text': '', 'sourceLabel': newHeadBlock['sourceLabel'], 'lineNumber': newHeadBlock['lineNumber']}
        self.addLead(lead)

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
                # ATTN: normally $functions are kept with the text and would be CAPTURED inside an $inline() operation that captures subsequent text
                # so if you want to STOP the inlining and start some new text you COULD put {} on a line of its own
                # but this is a bit annoying and error prone, and a very commmon thing to want to do is have an "Otherwise..." text that separates inline blocks
                # so here we allow the use of a $otherwise function which just inserts the text "otherwise" and specially treat this as something that STOPS the globbing of inline blocks
                # but as a kludge we have to tell our caller than an extra linebreak is needed.
                codeText = block['text']
                if (codeText.startswith('otherwise')):
                    # kludge to handle lack of linebreak
                    addTextSuffix = '\n'
                    # stop inline globbing
                    break

            # move this bock
            self.addChildBlock(newHeadBlock, block)
            del headBlock['blocks'][blockIndex]
            blockIndex -= 1

        # now process it (it will not be processed in main loop since it is added after)
        self.processLead(lead)

        return [lead, addTextSuffix]
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
    def makeTextLinkToLead(self, lead, flagVerboseLabel):
        properties = lead['properties']
        leadId = lead['id']
        leadLabel = properties['label']
        renderId = properties['renderId']
        return self.makeTextLinkToLeadId(leadId, renderId, leadLabel, flagVerboseLabel)


    def makeTextLinkToLeadId(self, leadId, renderId, leadLabel, flagVerboseLabel):
        if (renderId[0].isdigit()):
            prefix='#'
        else:
            prefix = ''
        #
        linkId = self.safeMarkdownId(renderId)
        label = renderId
        if (flagVerboseLabel) and (leadLabel!='') and (leadLabel is not None):
            if (leadLabel is not None):
                # fixup for markdown problems
                if ('(' in leadLabel) or ('[' in leadLabel):
                    leadLabel =''
            label += ': ' + leadLabel
        #
        if (self.isRenderTextSyntaxMarkdown()):
            text = '{}[{}](#{})'.format(prefix, label, linkId)
        else:
            text = prefix + label
        #
        return text


    def makeInserTagLabelText(self, tagLabel):
        if (self.isRenderTextSyntaxMarkdown()):
            text = '"**{}**"'.format(tagLabel)
        else:
            text = '"{}"'.format(tagLabel)
        return text


    def safeMarkdownId(self, idStr):
        idStr = idStr.replace(' ','_')
        return idStr
# ---------------------------------------------------------------------------

















# ---------------------------------------------------------------------------
    def getTagLabelForDisplay(self, tagDict):
        return tagDict['label']

    def getTagLabelForReport(self, tagDict):
        optionUseTagLetters = self.getTagsAsLetters()
        if (optionUseTagLetters):
            # report text gets more info
            return '{} ({})'.format(tagDict['label'], tagDict['id'])
        else:
            return tagDict['label']

    def appendUseNoteToTagDict(self, tagDict, text, leadInfoText, leadInfoMText, block):
        noteDict = self.makeDualNote(text, leadInfoText, leadInfoMText, block)
        tagDict['useNotes'].append(noteDict)


    def appendUseNoteDual(self, text, leadInfoText, leadInfoMText, block):
        noteDict = self.makeDualNote(text, leadInfoText, leadInfoMText, block)
        self.notes.append(noteDict)

    def makeDualNote(self, text, leadInfoText, leadInfoMText, block):
        plainText = text + ' in {} from {} near line {}.'.format(leadInfoText, block['sourceLabel'], block['lineNumber']+1)
        mText = text + ' in {} from {} near line {}.'.format(leadInfoMText, block['sourceLabel'], block['lineNumber']+1)
        return {'text': plainText, 'mtext': mText}

    def appendWarningLead(self, text, lead):
        headBlock = lead['block']
        plainText = text + '; in lead {} from {} around line {}.'.format(lead['id'], headBlock['sourceLabel'], headBlock['lineNumber']+1)
        mText = text + '; in lead {} from {} around line {}.'.format(self.makeTextLinkToLead(lead, True), headBlock['sourceLabel'], headBlock['lineNumber']+1)
        noteDict = {'text': plainText, 'mtext': mText}
        self.warnings.append(noteDict)

    def addWarning(self, text, mtext = None):
        if (mtext is None):
            mtext = text
        self.warnings.append({'text': text, 'mtext': mtext})


    def updateMarkBoxTracker(self, boxType, amount, lead):
        if (not boxType in self.markBoxesTracker):
            self.markBoxesTracker[boxType] = {'useCount': 0, 'sumAmounts': 0, 'useNotes': []}
        self.markBoxesTracker[boxType]['useCount'] += 1
        self.markBoxesTracker[boxType]['sumAmounts'] += amount
        #
        headBlock = lead['block']
        text = 'Marking {} {} boxes'.format(amount, boxType)
        plainText = text + '; in lead {} from {} around line {}.'.format(lead['id'], headBlock['sourceLabel'], headBlock['lineNumber']+1)
        mText = text + '; in lead {} from {} around line {}.'.format(self.makeTextLinkToLead(lead, True), headBlock['sourceLabel'], headBlock['lineNumber']+1)
        noteDict = {'text': plainText, 'mtext': mText} 
        self.markBoxesTracker[boxType]['useNotes'].append(noteDict)
# ---------------------------------------------------------------------------








# ---------------------------------------------------------------------------
    def evaluateCodeBlock(self, block, lead, textPositionStyle, behalfLead, evaluationOptions):
        # note that now behalfLead is the lead that should be credited with any debug stats, and if it is None then do not count such stats
        # this is used so that we can regenerate leads in a debug mode and similar things without effecting such stats

        # options
        optionUseTagLetters = self.getTagsAsLetters()

        # initial values; the None for reportText says to copy from resultText
        codeResult = {}
        resultText = ''
        reportText = None

        # parse code
        codeText = block['text']
        [funcName, args, pos] = self.parseFunctionCallAndArgs(block, codeText)

        if (lead==behalfLead) or (behalfLead is None):
            leadInfoText = 'lead "{}"'.format(lead['id'])
            leadInfoMText = 'lead "{}"'.format(self.makeTextLinkToLead(lead, True))
        else:
            leadInfoText = 'lead "{}" [copied from "{}"]'.format(behalfLead['id'], lead['id'])
            leadInfoMText = 'lead "{}" [copied from "{}"]'.format(self.makeTextLinkToLead(behalfLead, True), self.makeTextLinkToLead(lead, True))

        if (funcName=='empty'):
            # just placeholder
            pass
        
        elif (funcName=='options'):
            # merge in options
            jsonOptionString = args['json']
            jsonOptions = json.loads(jsonOptionString)
            # set the WORKINGDIR options
            self.jroptionsWorkingDir.mergeRawDataForKey('options', jsonOptions)

        elif (funcName=='golead'):
            # replace with a lead's rendered id
            leadId = args['leadId']
            #
            existingLead = self.findLeadById(leadId, False)
            if (existingLead is None):
                self.raiseBlockException(block, 0, 'Unknown lead reference: "{}"'.format(leadId))
            #
            linkText = self.makeTextLinkToLead(existingLead, False)
            baseText = self.getText('goto') + ' ' + linkText
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText
            # mindmap
            self.createMindMapLinkLeadGoesToLead(lead, existingLead, False)

        # tag use

        elif (funcName=='tag'):
            # just replace with text referring to a tag
            # map it
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName, True)

            # track use
            if (behalfLead is not None):
                tagDict['useCount'] += 1
                self.appendUseNoteToTagDict(tagDict, 'Referred to', leadInfoText, leadInfoMText, block)

            # use it
            baseText = '{}'
            resultText = baseText.format(self.getTagLabelForDisplay(tagDict))
            reportText = baseText.format(self.getTagLabelForReport(tagDict))
            # mindmap
            self.createMindMapLinkLeadReferencesConcept(lead, tagDict['id'])

        elif (funcName=='gaintag'):
            # show someone text that they get a tag
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName, True)

            # track use
            if (behalfLead is not None):
                tagDict['useCount'] += 1
                self.appendUseNoteToTagDict(tagDict, 'Gained condition', leadInfoText, leadInfoMText, block)

            # use it
            if (optionUseTagLetters):
                baseText = 'You have gained the condition {}; please circle this letter in your records for later use (if you have not done so already).'
            else:
                baseText = 'You have gained the condition keyword {}; please note this keyword in your records for later use (if you have not done so already).'
            #
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText.format(self.getTagLabelForDisplay(tagDict))
            reportText = baseText.format(self.getTagLabelForReport(tagDict))
            # mindmap
            self.createMindMapLinkLeadProvidesConcept(lead, tagDict['id'])

        elif (funcName in ['havetag', 'havealltags', 'haveanytags', 'requiretag', 'requirealltags', 'requireanytags']):
            # show someone text that checking a tag
            tagName = args['tagName']
            # this is an AND for all tags
            tagNames = tagName.split(',')
            tagLabels = []

            for tag in tagNames:
                tag = tag.strip()
                tagDict = self.findOrMakeTagDictForTag(tag, True)
                # track use
                if (behalfLead is not None):
                    tagDict['useCount'] += 1
                    self.appendUseNoteToTagDict(tagDict, 'Checking user has', leadInfoText, leadInfoMText, block)
                # use it
                tagLabel = self.makeInserTagLabelText(tagDict['label'])
                tagLabels.append(tagLabel)
                # mindmap
                self.createMindMapLinkLeadChecksConcept(lead, tagDict['id'])
            #
            if (funcName in ['haveanytags', 'requireanytags']):
                comboWord = 'or'
            else:
                comboWord = 'and'
            #
            numTags = len(tagNames)
            tagLabelsStr = jrfuncs.makeNiceCommaAndOrList(tagLabels, comboWord)

            if (funcName in ['requiretag', 'requirealltags', 'requireanytags']):
                # require tells people to go away unless they have something
                if (optionUseTagLetters):
                    baseText = 'If you have *NOT* gained (circled) the condition{} {{}}, stop reading now and return when you have.\n * Otherwise: go to '.format(jrfuncs.purals(numTags,'s'))
                else:
                    baseText = 'If you have *NOT* gained the condition keyword{} {{}}, stop reading now and return when you have.\n * Otherwise: go to '.format(jrfuncs.purals(numTags,'s'))
                codeResult['action'] = 'inline'
                codeResult['args'] = []
            else:
                if (optionUseTagLetters):
                    baseText = 'If you have gained (circled) the condition{} {{}}'.format(jrfuncs.purals(numTags,'s'))
                else:
                    baseText = 'If you have gained the condition keyword{} {{}}'.format(jrfuncs.purals(numTags,'s'))
            #
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText.format(self.getTagLabelForDisplay(tagDict))
            reportText = baseText.format(self.getTagLabelForReport(tagDict))


        elif (funcName=='missingtag'):
            # show someone text that checking a tag
            tagName = args['tagName']
            tagDict = self.findOrMakeTagDictForTag(tagName, True)

            # track use
            if (behalfLead is not None):
                tagDict['useCount'] += 1
                self.appendUseNoteToTagDict(tagDict, 'Checking user does not have', leadInfoText, leadInfoMText, block)

            # use it
            tagLabel = self.makeInserTagLabelText(tagDict['label'])
            if (optionUseTagLetters):
                baseText = 'If you have *NOT* gained (circled) the condition {}'
            else:
                baseText = 'If you have *NOT* gained the condition keyword {}'
            #
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText.format(self.getTagLabelForDisplay(tagDict))
            reportText = baseText.format(self.getTagLabelForReport(tagDict))
            # mindmap
            self.createMindMapLinkLeadChecksConcept(lead, tagDict['id'])


        elif (funcName in ['beforeday', 'afterday', 'onday']):
            day = int(args['day'])
            virtualTagName = '{}_{}'.format(funcName,day)
            # look up tag, do NOT convert to letter
            tagDict = self.findOrMakeTagDictForTag(virtualTagName, False)

            # track use
            if (behalfLead is not None):
                tagDict['useCount'] += 1
                self.appendUseNoteToTagDict(tagDict, 'Checking user has day condition ', leadInfoText, leadInfoMText, block)

            # use it
            tagLabel = self.makeInserTagLabelText(tagDict['label'])
            if (funcName == 'beforeday'):
                coreText = 'before day'
            elif (funcName == 'afterday'):
                coreText = 'after day'
            elif (funcName == 'onday'):
                coreText = 'day'
            baseText = 'If it is {} {}'.format(coreText, day)
            #
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText.format(self.getTagLabelForDisplay(tagDict))
            # mindmap
            self.createMindMapLinkLeadChecksConcept(lead, tagDict['id'])

        elif (funcName == 'ifcond'):
            cond = int(args['cond'])
            condClean = cond.replace(' ','')
            virtualTagName = '{}_{}'.format('cond',condClean)
            # look up tag, do NOT convert to letter
            tagDict = self.findOrMakeTagDictForTag(virtualTagName, False)

            # track use
            if (behalfLead is not None):
                tagDict['useCount'] += 1
                self.appendUseNoteToTagDict(tagDict, 'Checking user has generic condition ', leadInfoText, leadInfoMText, block)

            # use it
            tagLabel = self.makeInserTagLabelText(tagDict['label'])
            coreText = cond
            baseText = 'If it is {} {}'.format(coreText, day)
            #
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText.format(self.getTagLabelForDisplay(tagDict))
            # mindmap
            self.createMindMapLinkLeadChecksConcept(lead, tagDict['id'])


        elif (funcName=='inline'):
            # tricky one, this moves the subsqeuent text blocks into a new dynamically assigned lead and returns the lead #
            codeResult['action'] = 'inline'
            codeResult['args'] = args

        elif (funcName=='endjump'):
            # tricky one, this moves the subsqeuent text blocks into a new dynamically assigned lead and returns the lead #
            pass

        elif (funcName=='insertlead'):
            # embed contents of a lead here
            leadId = args['leadId']
            existingLead = self.findLeadById(leadId, False)
            if (existingLead is None):
                self.raiseBlockException(block, 0, 'Unknown lead reference: "{}"'.format(leadId))
            # ATTN: this RE-EVALUATES the lead text, but it would probably be better to use pre-evaluated text; the only problem is if a lead is INSERTED before it is defined
            # we COULD throw an error in this case (bad), or instead defer evaluation until later by doing this in two passes?
            # the one thing that could get messed up by this is any debug statistics and reporting that may get confused by us calling this on behalf of another lead
            # for example, our stats of recording when a tag is used will be confused into thinking the inserted lead used a tag twice instead of THIS lea
            [resultText, reportText] = self.evaluateHeadBlockTextCode(existingLead, lead, evaluationOptions)

        elif (funcName=='get'):
            # insert contents of a lead here
            varName = args['varName']
            [resultText, reportText] = self.getUserVariableTuple(varName)

        elif (funcName=='set'):
            # insert contents of a lead here
            varName = args['varName']
            varVal = args['value']
            self.setUserVariable(varName, varVal)

        elif (funcName=='markdemerit'):
            # insert contents of a lead here
            amount = int(args['amount']) if ('amount' in args) else 1
            self.updateMarkBoxTracker('demerit', amount, lead)
            text = 'Mark {} demerit{} in your case log.'.format(amount, jrfuncs.purals(amount,'s'))
            text = self.modifyTextToSuitTextPositionStyle(text, textPositionStyle, '* ')
            resultText = text

        elif (funcName=='markovertime'):
            # insert contents of a lead here
            amount = int(args['amount']) if ('amount' in args) else 1
            self.updateMarkBoxTracker('overtime', amount, lead)
            text = 'Mark {} overtime checkbox{} in your case log.'.format(amount, jrfuncs.purals(amount,'es'))
            text = self.modifyTextToSuitTextPositionStyle(text, textPositionStyle, '* ')
            resultText= text

        elif (funcName=='markculture'):
            # insert contents of a lead here
            amount = int(args['amount']) if ('amount' in args) else 1
            self.updateMarkBoxTracker('culture', amount, lead)
            text = 'Mark {} culture checkbox{} in your case log.'.format(amount, jrfuncs.purals(amount,'es'))
            text = self.modifyTextToSuitTextPositionStyle(text, textPositionStyle, '* ')
            resultText = text

        elif (funcName=='headback'):
            # insert contents of a lead here
            amount = int(args['demerits']) if ('demerits' in args) else 1
            gotoQuestion = args['goto'] if ('goto' in args) else ''
            if (gotoQuestion==''):
                text = 'Mark {} demerit checkbox{} in your case log and return to the field.  Then resume the questionnaire after you accomplish this'.format(amount, jrfuncs.purals(amount,'es'))
            else:
                text = 'Mark {} demerit checkbox{} in your case log and return to the field.  Then resume at question "{}" if you can accomplish this; if you need more help continue reading..'.format(amount, jrfuncs.purals(amount,'es'), gotoQuestion)                
            text = self.modifyTextToSuitTextPositionStyle(text, textPositionStyle, '* ')
            resultText = text

        elif (funcName=='retrieve'):
            # insert contents of a lead here
            label = args['label']
            comment = args['comment'] if ('comment' in args) else ''
            noteText = 'Player gets document "{}" ({})'.format(label, comment)
            self.appendUseNoteDual(noteText, leadInfoText, leadInfoMText, block)
            #
            baseText = 'Retrieve {}'
            baseText = self.modifyTextToSuitTextPositionStyle(baseText, textPositionStyle, '* ')
            resultText = baseText.format(label)
            if (comment != ''):
                reportText = baseText.format('{} ({})'.format(label,comment))

        elif (funcName=='form'):
            # insert contents of a lead here
            typeStr = args['type']
            shortInputText = '_ _ _ _ _ _ _ _ _ _ _ _ _'
            if (typeStr=='short'):
                text = shortInputText
            elif (typeStr=='long'):
                text =    '_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ <br/>\n'
            elif (typeStr=='multiline'):
                oneLine = '_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ <br/>\n'
                text = ('    ' + oneLine ) * 6
            elif (typeStr=='choice'):
                choices = args['choices'].split(';')
                text = ''
                for i,choiceVal in enumerate(choices):
                    choiceVal = choiceVal.strip()
                    text += ' {}. {}\n'.format(i,choiceVal)
            else:
                self.raiseBlockException(block, 0, 'Unknown form type: "{}"'.format(typeStr))
            resultText = text

        elif (funcName=='report'):
            # just a comment to show in the report only
            reportText = '**REPORT NOTE**: {}'.format(args['comment'])

        elif (funcName=='otherwise'):
            text = 'Otherwise'
            text = self.modifyTextToSuitTextPositionStyle(text, textPositionStyle, '* ')
            resultText = text

        else:
            # debug
            dbgObj = {'funcName': funcName, 'args': args, 'pos': pos}
            text = json.dumps(dbgObj)
            resultText = text
            jrprint('WARNING: code function not understood: {}'.format(text))

        # store results
        codeResult['text'] = resultText
        if (reportText is None):
            reportText = resultText
        codeResult['reportText'] = reportText

        return codeResult
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
    # user setable variables
    def getUserVariableTuple(self, varName):
        # specials
        if (varName=='buildInfo'):
            text = 'built {} v{}'.format(jrfuncs.getNiceCurrentDateTime(), self.getVersion())
            textReport = 'DEBUG REPORT - ' + text
            return [text, textReport]
        return [self.userVars[varName], None]
    
    def getUserVariable(self, varName):
        # specials
        if (varName=='buildInfo'):
            buildStr = 'built {} v{}'.format(jrfuncs.getNiceCurrentDateTime(), self.getVersion())
            return {'value':buildStr}
        return self.userVars[varName]

    def setUserVariable(self, varName, value):
        if (varName not in self.userVars):
            self.userVars[varName] = {}
        self.userVars[varName]['value'] = value


    def getText(self, varName, defaultVal=None):
        if (varName in self.userVars):
            return self.userVars[varName]
        if (varName in self.tText):
            return self.tText[varName]
        if (defaultVal is not None):
            return defaultVal
        raise Exception('Unknown text template var {}.'.format(varName))
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
    def getTagsAsLetters(self):
        return self.getOptionVal('tagsAsLetters', False)


    def findOrMakeTagDictForTag(self, tagName, flagConverToLetterIfEnabled):
        tagName = tagName.upper()
        if (tagName in self.tagMap):
            tagDict = self.tagMap[tagName]
        else:
            label = self.makeTagLabel(tagName, flagConverToLetterIfEnabled)
            tagDict = {'id': tagName, 'label': label, 'useCount': 0, 'useNotes': []}
            self.tagMap[tagName] = tagDict
        return tagDict


    def makeTagLabel(self, tagName, flagConverToLetterIfEnabled):
        #
        optionUseTagLetters = self.getTagsAsLetters()

        # use random letters as tags
        if (optionUseTagLetters) and (flagConverToLetterIfEnabled):
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
    def renderLeadsDual(self):
        self.renderLeads({'suffix':'', 'mode': 'normal'})
        self.renderLeads({'suffix':'Report', 'mode': 'report'})


    def renderLeads(self, leadOutputOptions):
        jrprint('Rendering leads..')

        # options
        renderOptions = self.getOptionValThrowException('renderOptions')
        renderFormat = renderOptions['format']
        optionCssdocstyle = self.getOptionValThrowException('cssdocstyle')
        #
        info = self.getOptionValThrowException('info')
        chapterName = jrfuncs.getDictValueOrDefault(info, 'chapterName', '')
        chapterTitle = jrfuncs.getDictValueOrDefault(info, 'chapterTitle', '')
        if (chapterTitle==''):
            chapterTitle = chapterName
        chapterAuthor = jrfuncs.getDictValueOrDefault(info, 'author', '')
        chapterVersion = jrfuncs.getDictValueOrDefault(info, 'version', '')
        chapterDate = jrfuncs.getDictValueOrDefault(info, 'date', '')
        buildDate = jrfuncs.getNiceCurrentDateTime()

        if (renderFormat!='html'):
            raise Exception('Only html lead rendering currently supported, not "{}".'.format(renderFormat))

        # where to save
        baseOutputFileName = chapterName + leadOutputOptions['suffix']
        defaultSaveDir = self.getOptionValThrowException('savedir')
        saveDir = self.getOptionVal('chapterSaveDir', defaultSaveDir)
        saveDir = self.resolveTemplateVars(saveDir)
        jrfuncs.createDirIfMissing(saveDir)
        outFilePath = '{}/{}.html'.format(saveDir, baseOutputFileName)

        # options
        rstate = {'optionCssdocstyle': optionCssdocstyle}

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
            html += '<!-- BUILT {} -->\n'.format(jrfuncs.getNiceCurrentDateTime())
            html += '</head>\n'
            html += '<body>\n\n\n'
            outfile.write(html)

            # optional front section
            templateFlePath = '{}/{}_front.html'.format(saveDir,chapterName)
            templateFlePath = self.resolveTemplateVars(templateFlePath)
            templateText = jrfuncs.loadTxtFromFile(templateFlePath, False)
            if (templateText is not None):
                outfile.write(templateText)

            # leads start
            html = '<div class="hlbook {}">\n\n'.format(optionCssdocstyle)
            outfile.write(html)

            # recursively render sections and write leads, starting from root
            self.renderSection(self.rootSection, outfile, renderFormat, rstate, [], leadOutputOptions)

            # book end
            html = '</div> <!-- hlbook -->\n'
            outfile.write(html)

            # optional back section
            templateFlePath = '{}/{}_back.html'.format(saveDir,chapterName)
            templateFlePath = self.resolveTemplateVars(templateFlePath)
            templateText = jrfuncs.loadTxtFromFile(templateFlePath, False)
            if (templateText is not None):
                outfile.write(templateText)


            # doc end
            html = '</body>\n'
            outfile.write(html)



    def renderSection(self, section, outfile, renderFormat, rstate, skipSectionList, leadOutputOptions):
        # special?
        if ('id' in section):
            if (section['id']=='debugReport'):
                # special automatic debugReport section
                outMode = leadOutputOptions['mode']
                if (outMode == 'report'):
                    self.renderDebugReportSection(section, outfile, renderFormat, rstate, leadOutputOptions)
                else:
                    # do not show this section if not in report mode
                    return


        # leads
        if ('leads' in section):
            leads = section['leads']
            if (len(leads)>0):
                self.renderSectionLeads(leads, section, outfile, renderFormat, rstate, leadOutputOptions)
        else:
            # blank leads just show section page?
            pass

        # recurse children
        if ('sections' in section):
            childSections = section['sections']
            for childid, child in childSections.items():
                if (childid not in skipSectionList):
                    self.renderSection(child, outfile, renderFormat, rstate, skipSectionList, leadOutputOptions)





    def renderSectionLeads(self, leads, section, outfile, renderFormat, rstate, leadOutputOptions):
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

        optionCssdocstyle = rstate['optionCssdocstyle']
        sectionCssStyle = jrfuncs.getDictValueOrDefault(section, 'cssStyle', '')
        if (sectionCssStyle==''):
            sectionCssStyle = optionCssdocstyle
        else:
            if (optionCssdocstyle != sectionCssStyle):
                # add, but make sure later overrides former in css (onecolumn beats twocolumn)
                sectionCssStyle = optionCssdocstyle + ' ' + sectionCssStyle

        # options
        outMode = leadOutputOptions['mode']

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
                html += '\n\n\n<article class="leads {}">\n'.format(sectionCssStyle)

                html += '<div class="leadsection {}">\n'.format(sectionCssStyle)
                # section breaks
                if (renderSectionHeaders):
                    if (sectionLabel!=''):
                        html += '\n\n<h1>{}</h1>\n\n'.format(sectionLabel)

            # lead start
            html += '<div id="{}" class="lead">\n'.format(self.safeMarkdownId(id))

            # lead label
            if (not jrfuncs.getDictValueOrDefault(leadProperties, 'noid', False)):
                html += '<h2>{}</h2>\n'.format(id)
            
            leadLabel = jrfuncs.getDictValueOrDefault(leadProperties,'label', '')
            if (leadLabel is None):
                leadLabel = ''
            if (renderLeadLabels) and (leadLabel!=''):
                leadLabelHtml = self.renderTextSyntaxForLabel(renderTextSyntax, leadLabel)
                html += '<h3>{}</h3>\n'.format(leadLabelHtml)

            # what are we outputting, normal text or report text?
            if (outMode=='normal'):
                leadText = lead['text']
            elif (outMode=='report'):
                leadText = lead['reportText']
            else:
                raise Exception('Unknown lead output mode, should be normal|report')
            #
            txtRenderedToHtml = self.renderTextSyntax(renderTextSyntax, leadText)
            html += '<div class="leadtext">{}</div>\n\n'.format(txtRenderedToHtml)

            # lead end
            html += '</div> <!-- lead -->\n'

            if (jrfuncs.getDictValueOrDefault(leadProperties, 'pageBreakAfter', False)):
                if (not 'solo' in optionCssdocstyle):
                    html += '<div class="pagebreakafter"></div>\n'

        # end of leads in this section
        if (showedHead):
            html += '</div> <!-- lead section -->\n\n'
            html += '</article>\n\n\n\n'

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
    

    def renderTextSyntaxForLabel(self, renderTextSyntax, text):
        html = self.renderTextSyntax(renderTextSyntax, text)
        html = re.sub(r'<p>(.*)<\/p>',r'\g<1>', html)
        html = html.strip()
        return html


    def renderMarkdown(self, text):
        return self.hlMarkdown.renderMarkdown(text)
# ---------------------------------------------------------------------------




















# ---------------------------------------------------------------------------
    def saveAllManualLeads(self):
        info = self.getOptionValThrowException('info')
        forceSourceName = jrfuncs.getDictValueOrDefault(info, 'chapterName', '')
        if (forceSourceName==''):
            forceSourceName = jrfuncs.getDictValueOrDefault(info, 'chapterTitle', '')
        if (forceSourceName==''):
            forceSourceName = 'hlp'
        else:
            forceSourceName = 'hlp_' + forceSourceName
        self.saveFictionalLeadsMadeManual(forceSourceName)

        

    def saveFictionalLeadsMadeManual(self, forceSourceLabel):
        # go through all the leads, find refereneces to fictional people and places, then output them to a file that could be dumped into MANUAL list
        fictionalSourceList = ['yellow', 'places_yellow', 'people', 'places_people']
        #
        jrprint('In saveFictionalLeadsMadeManual..')
        leadFeatures = {}
        countAllLeads = 0
        for lead in self.leads:
            countAllLeads += 1
            leadProprties = lead['properties']
            #
            leadId = leadProprties['id']
            #
            [existingLeadRow, existingRowSourceKey] = self.hlapi.findLeadRowByLeadId(leadId)
            if (existingLeadRow is None):
                continue
            existingLeadRowProperties = existingLeadRow['properties']
            #
            source = existingLeadRowProperties['source'] if ('source' in existingLeadRowProperties) else existingRowSourceKey
            ptype = existingLeadRowProperties['ptype']

            # add only fictional to special fictional files
            if (source in fictionalSourceList):
                # add it to save list
                if (ptype not in leadFeatures):
                    leadFeatures[ptype] = []
                # copy row and change some features
                propCopy = jrfuncs.deepCopyListDict(existingLeadRow['properties'])
                propCopy['jfrozen'] = 110
                propCopy['source'] = forceSourceLabel
                featureRow = {"type": "Feature", "properties": propCopy}
                #
                leadFeatures[ptype].append(featureRow)

            # add all rows to formap, and this time also add geometry
            fname = 'allForMapping'
            if (fname not in leadFeatures):
                leadFeatures[fname] = []
            # copy row and change some features
            propCopy = jrfuncs.deepCopyListDict(existingLeadRow['properties'])
            propCopy['jfrozen'] = 110
            propCopy['source'] = forceSourceLabel
            geometry = existingLeadRow['geometry']
            featureRow = {"type": "Feature", "properties": propCopy, "geometry": geometry}
            #
            leadFeatures[fname].append(featureRow)            

        # save
        saveDir = self.getOptionValThrowException('savedir')
        saveDir = self.resolveTemplateVars(saveDir)
        jrfuncs.createDirIfMissing(saveDir)
        
        encoding = self.getOptionValThrowException('storyFileEncoding')
        for ptype, features in leadFeatures.items():
            outFilePath = saveDir + '/manualAdd_{}.json'.format(ptype)
            
            # we write it out with manual text so that we can line break in customized way
            with open(outFilePath, 'w', encoding=encoding) as outfile:
                text = '{\n"type": "FeatureCollection",\n"crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:EPSG::2263" } },\n"features": [\n'
                outfile.write(text)
                numRows = len(features)
                for i, row in enumerate(features):
                    json.dump(row, outfile)
                    if (i<numRows-1):
                        outfile.write(',\n')
                    else:
                        outfile.write('\n')
                text = ']\n}\n'
                outfile.write(text)
            #
            jrprint('   wrote {} of {} leads to {}.'.format(len(features), countAllLeads, outFilePath))
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
    def calcLeadLabelForLeadRow(self, leadRow):
        if (leadRow is None):
            return ''
        leadRowProperties = leadRow['properties']
        leadRowLabel = leadRowProperties['dName']
        leadRowAddress = leadRowProperties['address']
        if (leadRowProperties['listype'] == 'private') or (leadRowAddress==''):
            label = leadRowLabel
        else:
            label = '{} @ {}'.format(leadRowLabel, leadRowAddress)
        return label
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
    def renderDebugReportSection(self, section, outfile, renderFormat, rstate, leadOutputOptions):
        # ATTN: this is ugly duplicative code with renderSection -- you need to merge it in better later

        # section header
        sectionLabel = section['label']

        optionCssdocstyle = rstate['optionCssdocstyle']
        sectionCssStyle = jrfuncs.getDictValueOrDefault(section, 'cssStyle', '')
        if (sectionCssStyle==''):
            sectionCssStyle = optionCssdocstyle
        else:
            if (optionCssdocstyle != sectionCssStyle):
                # add, but make sure later overrides former in css (onecolumn beats twocolumn)
                sectionCssStyle = optionCssdocstyle + ' ' + sectionCssStyle
        #
        html = ''

        # start
        html += '\n\n\n<article class="report {}">\n'.format(sectionCssStyle)
        html += '\n\n<h1>{}</h1>\n\n'.format(sectionLabel)

        # debug report core
        mtext = ''

        # basic stats
        leadCount = len(self.leads)
        blockTextLen = 0
        for i in range(0, leadCount):
            lead = self.leads[i]
            blockTextLen += len(lead['text'])
        #
        mtext += '## Basic Info\n\n'
        mtext += ' * Base options: {}.\n'.format(self.jroptions.getAllBlocks())
        mtext += ' * Working dir options: {}.\n'.format(self.jroptionsWorkingDir.getAllBlocks())
        mtext += ' * Scan found {} lead files: {}.\n'.format(len(self.storyFileList), self.storyFileList)
        mtext += ' * Leads found: {} ({}k of text).\n'.format(leadCount, int(blockTextLen/1000))
        mtext += '\n\n\n'

        # warnings
        mtext += '## {} Warnings\n\n'.format(len(self.warnings))
        if (len(self.warnings)==0):
            mtext += ' * No warnings encountered.\n'
        else:
            for index, note in enumerate(self.warnings):
                noteMtext = note['mtext']
                mtext += ' * [{}]: {}\n'.format(index+1, noteMtext)
        mtext += '\n\n\n'

        # notes
        mtext += '## {} Notes\n\n'.format(len(self.notes))
        if (len(self.notes)==0):
            mtext += ' * No notes.\n'
        else:
            for index, note in enumerate(self.notes):
                noteMtext = note['mtext']
                mtext += ' * [{}]: {}\n'.format(index+1, noteMtext)
        mtext += '\n\n\n'

        # tags
        mtext += '## {} Condition Tags\n\n'.format(len(self.tagMap))
        if (len(self.notes)==0):
            mtext += ' * No condition tags.\n'
        else:
            for index, tagDict in self.tagMap.items():
                id = tagDict['id']
                label = tagDict['label']
                if (id!=label):
                    labelstr = ': "{}"'.format(label)
                else:
                    labelstr = ''
                mtext += ' * [{}]{} was referred to {} times:\n'.format(id, labelstr, tagDict['useCount'])
                for index2, note in enumerate(tagDict['useNotes']):
                    noteMtext = note['mtext']
                    mtext += '   - {}\n'.format(noteMtext)
        mtext += '\n\n\n'

        # marks
        mtext += '## Checkbox Marking\n\n'
        if (len(self.notes)==0):
            mtext += ' * No checkboxes marked.\n'
        else:
            for boxType, trackDict in self.markBoxesTracker.items():
                mtext += ' * [{}]: instructed {} times for max total of {}:\n'.format(boxType, trackDict['useCount'], trackDict['sumAmounts'])
                for index2, note in enumerate(trackDict['useNotes']):
                    noteMtext = note['mtext']
                    mtext += '   - {}\n'.format(noteMtext)
        mtext += '\n\n\n'


        # lead list
        mtext += '## Lead List\n\n'
        for i in range(0, leadCount):
            lead = self.leads[i]
            properties = lead['properties']
            leadLabel = properties['label']
            if (properties['label'] is not None):
                leadStr = '{}:{}'.format(self.makeTextLinkToLead(lead, False), leadLabel)
            else:
                leadStr = self.makeTextLinkToLead(lead, False)
            mtext += ' * {} ...... {}\n'.format(leadStr, lead['debugInfo'])

        mtext += '\n\n'

        html += self.renderTextSyntax('markdown', mtext)

        # end
        html += '</article>\n\n\n\n'

        # write it
        outfile.write(html)
# ---------------------------------------------------------------------------








# ---------------------------------------------------------------------------
# mind map helpers

    def mindMapLead(self, lead):
        # mindmap
        self.createMindMapLeadNode(lead)


    def postProcesMindMap(self):
        # add neighborhood connects
        leadCount = len(self.leads)
        for i in range(0,leadCount):
            lead = self.leads[i]
            leadId = lead['id']
            mindMapLeadNode = self.mindMap.findNodeById(leadId)
            if (mindMapLeadNode is None):
                raise Exception('Could not find mindMapLeadNode.')
            self.postProcesMindMapLeadNode(lead, mindMapLeadNode)


    def postProcesMindMapLeadNode(self, lead, node):
        # mindmap link to neighborhood
        optionMakeNeighborHoodLinks = False

        if (optionMakeNeighborHoodLinks):
            existingLeadRow = lead['existingLeadRow']
            if (existingLeadRow is not None):
                jregion = existingLeadRow['properties']['jregion']
                jregionMindMapNode = self.createMindMapJregionNodeIfNeeded(jregion)
                # link from the lead to the neighborhood, since the lead SUGGESTS the concept of the neighborhood
                lProps = {'mtype': 'suggests'}
                link = self.mindMap.createLink(node, jregionMindMapNode, lProps)
                self.mindMap.addLink(link) 


    def createMindMapLeadNode(self, lead):
        leadProperties = lead['properties']
        # add mindmap node
        id = lead['id']
        nprops = {}
        nprops['renderId'] = leadProperties['renderId']
        nprops['label'] = leadProperties['label']
        nprops['mtype'] = leadProperties['mtype']
        nprops['lead'] = lead
        #
        mindMapNode = self.mindMap.createNode(id, nprops)
        self.mindMap.addNode(mindMapNode)


    def createMindMapJregionNodeIfNeeded(self, jregion):
        # create neighborhood region node if needed
        if (jregion==''):
            return None
        existingMindMapNode = self.mindMap.findNodeById(jregion)
        if (existingMindMapNode is not None):
            return existingMindMapNode
        # create it
        id = jregion
        nprops = {}
        nprops['renderId'] = jregion
        nprops['label'] = jregion
        nprops['mtype'] = 'jregion'
        #
        mindMapNode = self.mindMap.createNode(id, nprops)
        self.mindMap.addNode(mindMapNode)
        return mindMapNode


    # creating links with code

    def createMindMapLinkLeadGoesToLead(self, fromLead, toLead, flagInline):
        fromNode = self.mindMap.findNodeById(fromLead['id'])
        toNode = self.mindMap.findNodeById(toLead['id'])
        if (flagInline):
            linkProps = {'mtype': 'inlines'}
        else:
            linkProps = {'mtype': 'goes_to'}            
        link = self.mindMap.createLink(fromNode, toNode, linkProps)
        self.mindMap.addLink(link)


    def createMindMapLinkLeadChecksConcept(self, lead, concept):
        toNode = self.mindMap.findNodeById(lead['id'])
        conceptNode = self.findOrCreateConceptNode(concept)
        linkProps = {'mtype': 'informs'}
        link = self.mindMap.createLink(conceptNode, toNode, linkProps)
        self.mindMap.addLink(link)


    def createMindMapLinkLeadReferencesConcept(self, lead, concept):
        return self.createMindMapLinkLeadRequiresConcept(lead, concept)


    def createMindMapLinkLeadProvidesConcept(self, lead, concept):
        fromNode = self.mindMap.findNodeById(lead['id'])
        conceptNode = self.findOrCreateConceptNode(concept)
        linkProps = {'mtype': 'provides'}
        link = self.mindMap.createLink(fromNode, conceptNode, linkProps)
        self.mindMap.addLink(link)

    def findOrCreateConceptNode(self, concept):
        conceptNode = self.mindMap.findNodeById(concept)
        if (conceptNode is None):
            # add it
            props = {'mtype': 'concept'}
            conceptNode = self.mindMap.createNode(concept, props)
            self.mindMap.addNode(conceptNode)
        return conceptNode


    def saveMindMapStuff(self):
        #outFilePath = self.calcOutFileDerivedName('MindMap.dot')
        #self.mindMap.renderToDotFile(outFilePath)
        outFilePath = self.calcOutFileDerivedName('MindMap.dot')
        self.mindMap.renderToDotImageFile(outFilePath)
# ---------------------------------------------------------------------------



