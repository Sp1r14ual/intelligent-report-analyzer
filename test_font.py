import pymupdf as fitz

doc = fitz.open()
page = doc.new_page()
# In PyMuPDF: Story with html
story = fitz.Story(html="<p>Привет, мир! Факультет ФПМИ. Сумма: 1450 человек.</p>")
body = story.body()
writer = fitz.DocumentWriter("test_story.pdf")
dev = writer.begin_page(page.rect)
story.place(page.rect)
story.draw(dev)
writer.end_page()
writer.close()

doc2 = fitz.open("test_story.pdf")
print("Extracted:", repr(doc2[0].get_text()))
doc2.close()

