import pintas

src = '''
panid "Test"
ulo "Test"
saludsod "Question?" "Answer."
pagbilangan "2099-12-31T23:59:59" "Soon"
pagsuratan "Name" "Type here"
ladawanan
ladawan "https://example.com/a.jpg"
ladawan "https://example.com/b.jpg"
murdong
'''
out, images = pintas.compile_pintas(src)
assert 'pintas-saludsod' in out
assert 'pintas-pagbilangan' in out
assert 'pintas-pagsuratan' in out
assert 'pintas-ladawanan' in out
assert images == []
print('new UI syntax: PASS')
