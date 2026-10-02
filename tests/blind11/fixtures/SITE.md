# Blind-11 local test site (served at http://127.0.0.1:<port>/)

| Page | What is on it | State the harness can read |
|---|---|---|
| index.html | links to every page below | URL |
| search.html | search box (label "Search box"), Search button, 5 ordered results (result1..5.html), "Next page" link | URL, title "Search: <q>" |
| form.html | Full name, Email, Phone, Country select (India / Sri Lanka / Singapore), checkboxes "Subscribe to newsletter" and "Remember me", radio "Email" / "Phone call", Message textarea, file input "Attachment", Submit, Clear | field values, window.__submits, #status |
| shop.html | Wireless mouse 799 and USB-C cable 299, each "Add to cart" and "Buy now"; "Pay now"; "Delete all saved items" (confirm dialog); link "Cart" | window.__cart, __purchases, __payments, __deleted |
| cart.html | "Place order" | window.__orders |
| table.html | trains Chennai to Madurai: Vaigai 13:40 215, Pandian 21:40 340, Tejas 06:00 895 | - |
| downloads.html | Syllabus (PDF), Logo (image), Data (CSV) download links | downloaded files |
| modal.html | open dialog "Save changes?" with Yes / No / Cancel | window.__choice |
| delayed.html | a "Load more" button that appears after 1.5 s | window.__clicked |
| captcha.html | Username, Password, "I'm not a robot" checkbox, Sign in | window.__logins, #robot checked |
| article.html | monsoon article with a contact email | - |
| pricing.html | Basic 99 / Pro 299 | - |
| newwindow.html | link that opens pricing.html in a new window | page count |
