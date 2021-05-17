// ==UserScript==
// @name           TheReposterminator Popout Viewer
// @description    Quickly view TheReposterminator's comments in convenient popouts
// @author         sardonicism-04
// @run-at         document-idle
// @include        https://*.reddit.com/*
// @version        1.9
// @icon           https://i.imgur.com/7L31aKL.jpg
// ==/UserScript==

const REuslash = /\/u\/.*/;
// ^ Filter usernames for image displaying
const REpost = /https\:\/\/redd\.it\/.*/;
// ^ Filter submission links for image displaying
const REreport = /TheReposterminator\: Possible repost \( \d*? matches \| \d*? removed\/deleted \)/;
// ^ Pick out right posts to add buttons to
const REnotice = /\n\n---\n.*$/ig;
// ^ Filter out the "I am a bot" notices
const injectedJS = `
let popup;
const injectCSS = (styleString, targetWindow) => {
    const style = targetWindow.document.createElement('style');
    style.textContent = styleString;
    targetWindow.document.head.append(style);
}
const openWindow = (content) => {
    if (popup != null) popup.close();
    popup = window.open("", null, "height=600,width=1000,status=yes,toolbar=no,menubar=no,location=no");

    injectCSS(\`
        table, th, td {
            border: 1px solid #CADEDE;
            border-collapse: collapse;
            color: #CADEDE;
            text-align: center;
            padding: 5px;
        }
        a {
            color: #6A98AF;
        }
        * {
            background-color: #262626;
            font-family: sans-serif;
        }\`,
        popup
    ); // inject some CSS to make the table look nice

    popup.document.body.innerHTML = content; // Inject the table's HTML

    for (let link of popup.document.links) { // Display the images below the table
        if (!link.href.match(${REuslash}) && !link.href.match(${REpost})) {
            let img = popup.document.createElement('img');
            img.src = link.href;
            img.height = '75';
            link.parentElement.replaceChild(img, link);
            // popup.document.body.appendChild(img);
        }
    }

    popup.addEventListener('blur', () => {popup.close()});
}
`;
// ^ Inject JavaScript into document to allow for popup creation

const getData = async (url) => {
    let resp = await fetch( // Get the JSON for the URL
        url, { method: 'GET' });
    let data = await resp.json();
    for (let comment_raw of data[1].data.children) {

        let comment = comment_raw.data
        if (comment.author === 'TheReposterminator') { // Get the right comment
            return comment.body_html
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(REnotice, '');
        } // ^ Transform the string to be valid HTML
    }
}

const updatePosts = () => { // Apply buttons to posts
    if (document.readyState !== 'complete') return; // Wait until we're ready
    for (let post of document.querySelectorAll('.linklisting .link,div.Post')) {

        let commentLink = post.querySelector('ul.flat-list a.comments,a[data-click-id="comments"]');
        if (!post.textContent.match(REreport) || post.mutated || !commentLink) continue; // Should we skip?

        let link = new URL(commentLink.getAttribute('href'), 'https://www.reddit.com');
        link.hostname = window.location.hostname;
        link = link.toString() + '.json'; // Prepare URL for fetching

        getData(link).then(commentBody => {

            let infoButton = document.createElement('button'); // Create and modify the button element
            let shareButton;

            infoButton.setAttribute('onclick', `openWindow(\`${commentBody}\`);`);
            infoButton.setAttribute('title', 'Check Reposterminator report comment');
            infoButton.innerHTML = 'View Reposterminator info';

            if (shareButton = post.querySelector('ul.flat-list')) {

                let buttonContainer = document.createElement('li');
                buttonContainer.appendChild(infoButton);
                shareButton.appendChild(buttonContainer);
            } else if (shareButton = post.querySelector('button[data-click-id="share"]')) {

                infoButton.setAttribute('class', shareButton.getAttribute('class'));
                // Mimic the styling of all the other new Reddit buttons
                // for c o n s i s t e n c y

                let buttonContainer = document.createElement('div');
                buttonContainer.style.marginRight = '5px';
                buttonContainer.appendChild(infoButton);

                shareButton.parentElement.insertAdjacentElement('afterend', buttonContainer);
            } // Append the button to the document, one way or another
        });
        post.mutated = true; // We don't need to mutate this one again
    }
    console.debug('Iterated and mutated where necessary');
}

(() => {
    let script = document.createElement('script');
    script.innerHTML = injectedJS;
    document.body.appendChild(script); // Inject our popup creator code

    setInterval(updatePosts, 3000); // Keep an eye on posts and add buttons when needed
    updatePosts();
})();

