console.log("MSH UI Loaded");
fetch('/api/catalog.json')
    .then(response => response.json())
    .then(data => {
        console.log("Catalog loaded:", data);
        document.getElementById('status').innerText = "Catalog Loaded: " + data.meta.project_name;
    })
    .catch(error => {
        console.error("Error loading catalog:", error);
        document.getElementById('status').innerText = "Error loading catalog";
    });
