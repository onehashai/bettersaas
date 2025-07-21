$(document).ready(function () {
    function addAIButton(timelineItem) {
        if (timelineItem.querySelector('.ai-generate-wrapper')) {
            return;
        }

        let wrapper = document.createElement('div');
        wrapper.className = 'ai-generate-wrapper';

        let mainBtn = document.createElement('button');
        mainBtn.className = 'btn btn-xs btn-secondary action-btn ai-btn';
        mainBtn.innerHTML = `
            <i class="fa fa-star" style="margin-right: 4px;"></i>
            Ask AI
        `;

        let dropdown = document.createElement('div');
        dropdown.className = 'ai-generate-dropdown';
        dropdown.style.display = 'none';

        let summarizeBtn = document.createElement('button');
        summarizeBtn.className = 'btn btn-xs btn-secondary ai-btn-options';
        summarizeBtn.innerHTML = `
            <i class="fa fa-list" style="margin-right: 4px;"></i>
            Summarize
        `;
        summarizeBtn.onclick = async () => {
            try {
                const doctype = frappe?.get_route()[1];
                const docname = frappe?.get_route()[2]; 

                if (!doctype || !docname) {
                    frappe.msgprint('Unable to identify document details');
                    return;
                }

                const metadata = await fetchCommunications(doctype, docname);
                window.CRMCopilotWidget.open(); 
                window.CRMCopilotWidget.sendMessage('Summarize Conversations', metadata);
                dropdown.style.display = 'none';
            } catch (error) {
                console.error('Error in summarize action:', error);
                frappe.msgprint('Error occurred while processing request');
            }
        };

        let writeEmailBtn = document.createElement('button');
        writeEmailBtn.className = 'btn btn-xs btn-secondary ai-btn-options';
        writeEmailBtn.innerHTML = `
            <i class="fa fa-envelope" style="margin-right: 4px;"></i>
            Write Email
        `;
        writeEmailBtn.onclick = () => {
            try {
                window.CRMCopilotWidget.open(); 
                window.CRMCopilotWidget.sendMessage('Write an email');
                dropdown.style.display = 'none';
            } catch (error) {
                console.error('Error in write email action:', error);
                frappe.msgprint('Error occurred while opening email composer');
            }
        };

        dropdown.appendChild(summarizeBtn);
        dropdown.appendChild(writeEmailBtn);

        mainBtn.onclick = function (e) {
            e.stopPropagation();
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        };

        wrapper.appendChild(mainBtn);
        wrapper.appendChild(dropdown);
        timelineItem.appendChild(wrapper);

        console.log('AI button added successfully');
    }

    function initializeAIButton() {
        const existingTimeline = document.querySelector('.timeline-items.timeline-actions');
        if (existingTimeline) {
            addAIButton(existingTimeline);
        }

        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        if (node.matches && node.matches('.timeline-items.timeline-actions')) {
                            addAIButton(node);
                        }
                        else if (node.querySelector) {
                            const timeline = node.querySelector('.timeline-items.timeline-actions');
                            if (timeline) {
                                addAIButton(timeline);
                            }
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: false,
            attributeOldValue: false,
            characterData: false,
            characterDataOldValue: false
        });
    }

    document.addEventListener('click', function (e) {
        const dropdowns = document.querySelectorAll('.ai-generate-dropdown');
        dropdowns.forEach(dropdown => {
            if (!dropdown.parentElement.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    });

    initializeAIButton();

    if (typeof frappe !== 'undefined') {
        frappe.router.on('change', function() {
            setTimeout(initializeAIButton, 500);
        });
    }
});

async function fetchCommunications(doctype, docname) {
    try {
        const res = await fetch(`/api/method/bettersaas.bettersaas.utils.get_all_communications?doctype=${doctype}&docname=${docname}`);
        
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        
        const data = await res.json();
        return data.message;
    } catch (error) {
        console.error('Error fetching communications:', error);
        frappe.msgprint('Error fetching conversation data');
        return [];
    }
}
