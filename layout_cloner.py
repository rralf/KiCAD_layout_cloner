#!/usr/bin/env python3

#Script for KiCAD Pcbnew to clone a part of a layout. The scipt clones a row or a matrce
#of similar layouts.
#
#For now, there are no command line parameters given for the script, instead
#all the settings are written in this file. Before using this script, you must have your schema
#ready.
#1. Use hierarchical sheets for the subschemas to be cloned and annotate them
#so that each sheet has module references starting with a different hundred.
#2. Import a netlist into Pcbnew and place all the components except the ones to be cloned.
#3. In the same board file, create also an optimal layout for the subschema to be used
#as the template for the clones.
#4. Surround the layout of the subchema with a zone in the comment layer.
#5. Save the .kicad_pcb file and run this script.
#
#The script has three main parts:
#First, the script moves the modules, which are already imported into the board file. They are
#moved by a predetermined offset amount compared to the template module. (A module with the same
#reference, except starting with a different hundred, eg. templatemodule = D201, clones = D301, D401, D501 etc.)
#Second, the script clones the zones inside the comment layer zone. It seems the zone to be cloned must
#be completely inside the comment zone. Zones have a net defined for them. The script searches for any
#pads inside the cloned zone and sets their net for the zone. So you may get a wrong zone for the net if
#there are pads with different nets inside the zone.
#Third, the script clones the tracks inside the comment zone. Any track touching the zone will be cloned.
#Tracks do not have nets defined for them so they should connect nicely to the modules they will be touching
#after the cloning process.
#
#This script has been tested with KiCAD version BZR 5382 with all scripting settings turned on. (Ubuntu and Python 2.7.6)
#The script can be run in Linux terminal with command $python pcbnew_cloner.py

import argparse
import sys
import re
from pcbnew import *

#Settings, modify these to suit your project

#The schematic with the hierarchical sheets (not used currently, requires utilizing kipy to parse schematic)
#You can copy the schema parsing with kipy for example from klonor-kicad if you have enough components to justify it
#schemaTemplate = './boosterilevy/booster.sch'
#Instead the components to be cloned are currently given manually

parser = argparse.ArgumentParser()

parser.add_argument('-d', default=100, type=int, help='Difference in the reference numbers between hierarchical sheet (default: %(default)s)')
parser.add_argument('-s', default=200, type=int, help='Starting point of numbering in the first hierarchical sheet (default: %(default)s)')
parser.add_argument('-x', default=11, type=float, help='Spacing between clones in x direction (default: %(default)s)')
parser.add_argument('-y', default=11, type=float, help='Spacing between clones in y direction (default: %(default)s)')
parser.add_argument('-X', default=4, type=int, help='Number of clones in x direction (default: %(default)s)')
parser.add_argument('-Y', default=4, type=int, help='Number of clones in y direction(default: %(default)s)')

parser.add_argument('input')
parser.add_argument('references')
parser.add_argument('output', nargs='?', default=None)
args = parser.parse_args()

with open(args.references, 'r') as f:
	templateReferences = f.read().split()

#The .kicad-pcb board with a ready layout for the area to be cloned.
#The cloned area must be surrounded by a (square) zone in the comment layer.
inputBoard = args.input

if args.output:
    outputBoardFile = args.output
else:
    outputBoardFile = args.input

templateRefModulo = args.d
templateRefStart = args.s
move_dx = FromMM(args.x)
move_dy = FromMM(args.y)
clonesX = args.X
clonesY = args.Y

numberOfClones = clonesX * clonesY
board = LoadBoard(inputBoard)

#Cloning the modules
for templateRef in templateReferences:							#For each module in the template schema
    templateModule = board.FindModuleByReference(templateRef)				#Find the corresponding module in the input board
    if templateModule is not None:
        cloneReferences = []
        templateReferenceNumber = (re.findall(r"\d+", templateRef)).pop(0)		#Extract reference number (as string)

        for i in range(0, numberOfClones-1):						#Create list of references to be cloned of this module in the template
            cloneRefNumber = int(templateReferenceNumber) + (i+1)*templateRefModulo	#Number of the next clone
            cloneReferences.append(re.sub(templateReferenceNumber, "", templateRef) + str(cloneRefNumber))	#String reference of the next clone
        print('Original reference: %s, Generated clone references: %s' % (templateRef, cloneReferences))

        for counter, cloneRef in enumerate(cloneReferences):				#Move each of the clones to appropriate location
            templatePosition = templateModule.GetPosition()
            cloneModule = board.FindModuleByReference(cloneRef)
            if cloneModule is not None:
                if cloneModule.GetLayer() is not templateModule.GetLayer():			#If the cloned module is not on the same layer as the template
                    cloneModule.Flip(wxPoint(1,1))						#Flip it around any point to change the layer
                vect = wxPoint(templatePosition.x+(counter+1)%clonesX*move_dx, templatePosition.y+(counter+1)//clonesX*move_dy) #Calculate new position
                cloneModule.SetPosition(vect)						#Set position
                cloneModule.SetOrientation(templateModule.GetOrientation())			#And copy orientation from template
            else:
                print('Module to be moved (%s) is not found in the board.' % cloneRef);
    else:
        print('Module %s was not found in the template board' % templateRef)
print('Modules moved and oriented according to template.')

#Cloning zones inside the template area.
#First lets use the comment zone to define the area to be cloned.
templateRect = None
for i in range(0, board.GetAreaCount()):
    zone = board.GetArea(i)
    if zone.GetLayer() == 41:								#Find the comment zone encasing the template board area
        templateRect = zone.GetBoundingBox()
        #board.RemoveArea(zone)								#Removing comment zone does not work
        print('Comment zone left top: %s width: %u height: %u' % (templateRect.GetOrigin(), templateRect.GetWidth(), templateRect.GetHeight()))

if not templateRect:
    print('Template Rect not found!')
    quit()

modules = board.GetModules()
#Then iterate through all the other zones and copy them
print('Iterating through all the pads for each cloned zone, might take a few seconds...')
for i in range(0, board.GetAreaCount()):						#For all the zones in the template board
    zone = board.GetArea(i)
    print('Original zone location %s' % zone.GetPosition())

    if templateRect.Contains(zone.GetPosition()) and zone.GetLayer() is not 41:		#If the zone is inside the area to be cloned (the comment zone) and it is not the comment zone (layer 41)
        for i in range(1, numberOfClones):						#For each target clone areas
            zoneClone = zone.Duplicate()						#Make copy of the zone to be cloned
            zoneClone.Move(wxPoint(i%clonesX*move_dx, i//clonesX*move_dy))		#Move it inside the target clone area
            for module in modules:								#Iterate through all the pads (also the cloned ones) in the board...
                for pad in module.Pads():
                    if zoneClone.HitTestInsideZone(pad.GetPosition()) and pad.IsOnLayer(zoneClone.GetLayer()):		#To find the (last) one inside the cloned zone. pad.GetZoneConnection() could also be used
                        zoneClone.SetNetCode(pad.GetNet().GetNet())			#And set the (maybe) correct net for the zone
            board.Add(zoneClone)								#Add to the zone board
print('Zones cloned.')

#Cloning tracks inside the template area
tracks = board.GetTracks()
cloneTracks = []
for track in tracks:
    if track.HitTest(templateRect):							#Find tracks which touch the comment zone
        for i in range(1, numberOfClones):						#For each area to be cloned
            cloneTrack = track.Duplicate()						#Copy track
            cloneTrack.Move(wxPoint(i%clonesX*move_dx, i//clonesX*move_dy))		#Move it
            cloneTracks.append(cloneTrack)						#Add to temporary list
for track in cloneTracks:								#Append the temporary list to board
    tracks.Append(track)
print('Tracks cloned.')

#Save output file
board.Save(outputBoardFile)
print('Script completed & output file saved.')
