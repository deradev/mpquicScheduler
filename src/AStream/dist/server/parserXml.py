from xml.dom import minidom

#xmldoc = minidom.parse('C:\\Users\\Thiago\\Desktop\\teste\\xml.mpd')
xmldoc = minidom.parse("C:\\Users\\pjuluri\\Documents\\GitHub\\AStream\\dist\\server\\media\\mpd\\x4ukwHdACDw.mpd")
itemlist = xmldoc.getElementsByTagName('Representation')

print ("Number of itens: " , len(itemlist))
#print len(itemlist)
#print itemlist[0].attributes['id'].value
for s in itemlist:
    print (s.attributes['id'].value , s.attributes['bandwidth'].value)
    #print s.attributes['bandwidth'].value

#dom1 = parse('C:\\Users\\Thiago\\Desktop\\teste\\xml.mpd')


