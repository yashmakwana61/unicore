const config = {
  title: 'Edicai Documentation',
  tagline: 'Manage the campus. Understand every workflow.',
  url: 'https://docs.edicai.com',
  baseUrl: '/',
  favicon: 'img/edicai-mark.svg',
  organizationName: 'yashmakwana61',
  projectName: 'unicore',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  i18n: {defaultLocale: 'en', locales: ['en']},
  presets: [['classic', {
    docs: {routeBasePath: 'docs',
      // Publish only screenshot-backed administrator workflow training.
      // Draft/source-only modules, workspace inventories and placeholders remain in Git.
      include: ['training/**/*.{md,mdx}'],
      sidebarPath: require.resolve('./sidebars.js'),
      editUrl: 'https://github.com/yashmakwana61/unicore/edit/main/docs-portal/'},
    blog: false,
    theme: {customCss: require.resolve('./src/css/custom.css')},
    sitemap: {changefreq: 'weekly', priority: 0.5}
  }]],
  themeConfig: {
    colorMode: {defaultMode: 'light', respectPrefersColorScheme: true},
    navbar: {title:'Edicai Docs', logo:{alt:'Edicai',src:'img/edicai-mark.svg'},
      items:[{type:'docSidebar',sidebarId:'main',position:'left',label:'Documentation'},
        {to:'/search',position:'left',label:'Search'},
        {href:'https://github.com/yashmakwana61/unicore',position:'right',label:'GitHub'}]},
    footer: {style:'light', links:[
      {title:'Training',items:[{label:'Administrator Guide',to:'/docs/training/overview'},{label:'Quick Reference',to:'/docs/training/quick_reference'}]},
      {title:'About',items:[{label:'Edicai',href:'https://edicai.com'},{label:'Precisefect',href:'https://precisefect.com'}]}
    ],copyright:'© Precisefect Solutions Pvt. Ltd.'},
    prism: {theme: require('prism-react-renderer').themes.github,
      darkTheme: require('prism-react-renderer').themes.dracula}
  }
};
module.exports=config;
