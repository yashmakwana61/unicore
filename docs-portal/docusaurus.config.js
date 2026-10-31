const config = {
  title: 'Clasflow Documentation',
  tagline: 'Manage the campus. Understand every workflow.',
  url: 'https://docs.clasflow.io',
  baseUrl: '/',
  favicon: 'img/clasflow-mark.svg',
  organizationName: 'yashmakwana61',
  projectName: 'unicore',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  i18n: {defaultLocale: 'en', locales: ['en']},
  presets: [['classic', {
    docs: {routeBasePath: 'docs', sidebarPath: require.resolve('./sidebars.js'),
      editUrl: 'https://github.com/yashmakwana61/unicore/edit/main/docs-portal/'},
    blog: false,
    theme: {customCss: require.resolve('./src/css/custom.css')},
    sitemap: {changefreq: 'weekly', priority: 0.5}
  }]],
  themeConfig: {
    colorMode: {defaultMode: 'light', respectPrefersColorScheme: true},
    navbar: {title:'Clasflow Docs', logo:{alt:'Clasflow',src:'img/clasflow-mark.svg'},
      items:[{type:'docSidebar',sidebarId:'main',position:'left',label:'Documentation'},
        {to:'/search',position:'left',label:'Search'},
        {href:'https://github.com/yashmakwana61/unicore',position:'right',label:'GitHub'}]},
    footer: {style:'light', links:[
      {title:'Explore',items:[{label:'Getting Started',to:'/docs/getting-started/overview'},{label:'All Modules',to:'/docs/reference/module-catalog'}]},
      {title:'About',items:[{label:'Clasflow',href:'https://clasflow.io'},{label:'Precisefect',href:'https://precisefect.com'}]}
    ],copyright:'© Precisefect Solutions Pvt. Ltd.'},
    prism: {theme: require('prism-react-renderer').themes.github,
      darkTheme: require('prism-react-renderer').themes.dracula}
  }
};
module.exports=config;
